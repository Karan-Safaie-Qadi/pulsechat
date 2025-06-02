import random

from pulsechat.bots import Bot, BotEngine, BotPersona, RATE_PRESETS
from pulsechat.handlers import ChatHandlers
from pulsechat.rooms import RoomRegistry
from pulsechat.sessions import Session, SessionRegistry
from pulsechat.storage import TranscriptStore


class FakeWriter:
    def __init__(self):
        self.frames = []

    def get_extra_info(self, name):
        return ("bot", 0) if name == "peername" else None

    def write(self, data):
        self.frames.append(data)


class MemoryStore(TranscriptStore):
    def __init__(self):
        self.entries = []
        self.root = None

    def append(self, entry):
        self.entries.append(entry)


def make_engine(count=4):
    handlers = ChatHandlers(
        sessions=SessionRegistry(),
        rooms=RoomRegistry(),
        store=MemoryStore(),
        history_limit=100,
    )
    return BotEngine(handlers, count=count, rate="normal", seed=42), handlers


class TestPersona:
    def test_actions_are_known(self):
        rng = random.Random(1)
        for kind in ("chatty", "lurker", "greeter", "questioner"):
            p = BotPersona(kind)
            for _ in range(50):
                assert p.next_action(rng) in ("chat", "react", "idle", "greet", "ask")

    def test_unknown_persona_defaults_idle(self):
        p = BotPersona("mystery")
        assert p.next_action(random.Random(0)) == "idle"


class TestBot:
    def test_compose_known_actions(self):
        handlers = ChatHandlers(
            sessions=SessionRegistry(), rooms=RoomRegistry(), store=MemoryStore()
        )
        bot = Bot("b0", BotPersona("chatty"), ["general"], handlers, (1.0, 2.0), seed=7)
        assert isinstance(bot.compose("chat"), str)
        assert bot.compose("idle") is None

    def test_think_time_within_rate(self):
        handlers = ChatHandlers(
            sessions=SessionRegistry(), rooms=RoomRegistry(), store=MemoryStore()
        )
        bot = Bot("b0", BotPersona("lurker"), ["general"], handlers, (4.0, 10.0), seed=3)
        for _ in range(200):
            t = bot.think_time()
            assert 4.0 <= t <= 40.0  # upper bound allows the distraction spike

    def test_pick_room_sticks_or_hops(self):
        handlers = ChatHandlers(
            sessions=SessionRegistry(), rooms=RoomRegistry(), store=MemoryStore()
        )
        bot = Bot("b0", BotPersona("chatty"), ["a", "b"], handlers, (1.0, 2.0), seed=5)
        for _ in range(30):
            assert bot.pick_room() in ("a", "b")


class TestBotEngine:
    def test_rate_presets_exist(self):
        assert set(RATE_PRESETS) == {"fast", "normal", "slow"}

    def test_creates_population(self):
        engine, handlers = make_engine(6)
        assert len(engine.bots) == 6
        assert len({b.name for b in engine.bots}) == 6






























