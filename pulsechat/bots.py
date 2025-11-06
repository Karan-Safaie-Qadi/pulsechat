"""Bot engine: fake participants that make the server feel alive.

Bots are asyncio tasks on the same loop as the server. Each bot owns a
persona (a small behavior kit) and runs a simple loop: pick an action
(chat / react / idle / hop rooms), sleep a human-ish amount, repeat.

The delays are sampled from asymmetric distributions rather than fixed
sleeps, so aggregate traffic does not look machine-stamped.
"""

from __future__ import annotations

import asyncio
import logging
import random

from pulsechat.handlers import ChatHandlers
from pulsechat.protocol import make_id, now_ts, sanitize_text

log = logging.getLogger(__name__)

PERSONAS = ("chatty", "lurker", "greeter", "questioner")

RATE_PRESETS = {
    # seconds between bot actions (min, max)
    "fast": (1.5, 6.0),
    "normal": (4.0, 15.0),
    "slow": (12.0, 40.0),
}

GREETINGS = (
    "salam everyone",
    "hi all",
    "hey",
    "hello hello",
    "afternoon folks",
)

CHAT_LINES = (
    "anyone tried the new build?",
    "reading the logs now, looks fine to me",
    "brb coffee",
    "that deploy went smoother than expected",
    "has anyone seen the issue tracker today?",
    "ok that fixed it, thanks",
    "the graph looks weird after 3pm",
    "wm, same here",
    "works on my machine :)",
    "adding it to my notes",
)

QUESTIONS = (
    "what time is the sync today?",
    "did the nightly run pass?",
    "which branch is hotfix on?",
    "anyone else getting timeouts?",
    "where do we track the flaky tests?",
    "is the staging env up?",
)

REACTIONS = (
    "good point",
    "+1",
    "haha yeah",
    "true",
    "agreed",
    "makes sense",
)


class BotPersona:
    """Behavior knobs for one bot archetype."""

    def __init__(self, kind: str) -> None:
        self.kind = kind

    def next_action(self, rng: random.Random) -> str:
        if self.kind == "chatty":
            return rng.choices(("chat", "react", "idle"), weights=(6, 2, 2))[0]
        if self.kind == "lurker":
            return rng.choices(("react", "idle", "chat"), weights=(3, 6, 1))[0]
        if self.kind == "greeter":
            return rng.choices(("greet", "chat", "idle"), weights=(3, 3, 4))[0]
        if self.kind == "questioner":
            return rng.choices(("ask", "react", "idle"), weights=(5, 2, 3))[0]
        return "idle"


class Bot:
    """One fake participant attached to the running server."""

    def __init__(
        self,
        name: str,
        persona: BotPersona,
        rooms: list[str],
        handlers: ChatHandlers,
        rate: tuple[float, float],
        seed: int | None = None,
    ) -> None:
        self.name = name
        self.persona = persona
        self.rooms = rooms
        self.handlers = handlers
        self.rate = rate
        self.rng = random.Random(seed)
        self.current_room = rooms[0] if rooms else "general"
        self.session = None  # attached by the engine when the server is up
        self.typing_until = 0.0

    def pick_room(self) -> str:
        if len(self.rooms) > 1 and self.rng.random() < 0.15:
            self.current_room = self.rng.choice(self.rooms)
        return self.current_room

    def compose(self, action: str) -> str | None:
        """Return the text for an action, or None for no-op actions."""
        if action == "greet":
            return self.rng.choice(GREETINGS)
        if action == "chat":
            return self.rng.choice(CHAT_LINES)
        if action == "ask":
            return self.rng.choice(QUESTIONS)
        if action == "react":
            return self.rng.choice(REACTIONS)
        return None

    def think_time(self) -> float:
        """Human-ish pause before an action: skewed, jittered, sometimes long."""
        lo, hi = self.rate
        base = self.rng.uniform(lo, hi)
        if self.rng.random() < 0.08:
            base *= self.rng.uniform(2.0, 4.0)  # got distracted
        return base


class BotEngine:
    """Owns the bot population and their asyncio tasks."""

    def __init__(
        self,
        handlers: ChatHandlers,
        count: int = 8,
        rate: str = "normal",
        seed: int | None = None,
    ) -> None:
        self.handlers = handlers
        self.rate = RATE_PRESETS.get(rate, RATE_PRESETS["normal"])
        self.bots: list[Bot] = []
        self._tasks: list[asyncio.Task] = []
        self._rng = random.Random(seed)
        self.bot_rooms = ["general", "random", "support"]
        for i in range(count):
            name = f"bot_{make_id()[:4]}_{i}"
            persona = BotPersona(PERSONAS[i % len(PERSONAS)])
            bot = Bot(
                name=name,
                persona=persona,
                rooms=self.bot_rooms,
                handlers=handlers,
                rate=self.rate,
                seed=self._rng.randrange(2**32),
            )
            self.bots.append(bot)

    async def start(self) -> None:
        """Register every bot as a session, then spawn its loop task."""
        loop = asyncio.get_running_loop()
        from pulsechat.sessions import Session

        for bot in self.bots:
            session = Session(sid=make_id(), name=bot.name, writer=NullWriter())
            session.registered_at = now_ts()
            self.handlers.sessions.add(session)
            for room in bot.rooms:
                room_obj = self.handlers.rooms.get_or_create(room)
                room_obj.add_member(session.sid)
                session.rooms.add(room)
            bot.session = session
            task = loop.create_task(self._run_bot(bot), name=f"bot:{bot.name}")
            self._tasks.append(task)
        log.info("started %d bots across %s", len(self.bots), ",".join(self.bot_rooms))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        for bot in self.bots:
            if bot.session is not None:
                self.handlers.sessions.remove(bot.session.sid)
                for room in bot.rooms:
                    room_obj = self.handlers.rooms.get(room)
                    if room_obj is not None:
                        room_obj.remove_member(bot.session.sid)

    async def _run_bot(self, bot: Bot) -> None:
        """Main loop for one bot: act, then sleep a human-ish interval."""
        await asyncio.sleep(self._rng.uniform(0.5, 3.0))
        while True:
            action = bot.persona.next_action(bot.rng)
            room = bot.pick_room()
            text = bot.compose(action)
            if text is not None and bot.session is not None:
                await asyncio.sleep(bot.think_time() * 0.4)  # "typing" pause
                frame = {"type": "msg", "room": room, "text": text}
                try:
                    self.handlers.dispatch(bot.session, frame)
                except Exception as exc:  # noqa: BLE001
                    log.debug("bot %s action failed: %s", bot.name, exc)
            await asyncio.sleep(bot.think_time())


class NullWriter:
    """Stand-in for a StreamWriter; bots write through handlers, not sockets."""

    def get_extra_info(self, _name: str) -> tuple[str, int] | None:
        return ("bot-loop", 0)

    def write(self, data: bytes) -> None:
        """Fanout may address bots directly; bytes go nowhere."""

    def is_closing(self) -> bool:
        return False


















































