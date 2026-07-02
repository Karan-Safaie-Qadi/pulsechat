"""Request handlers and dispatch.

Each handler takes (session, frame) and returns the reply payload, or raises
ProtocolError for client mistakes. Broadcast work happens through the fanout
helpers so handlers stay small and easy to unit-test without sockets.
"""

from __future__ import annotations

import logging

from pulsechat.protocol import (
    ProtocolError,
    encode_frame,
    make_id,
    now_ts,
    server_event,
)
from pulsechat.rooms import RoomRegistry
from pulsechat.sessions import Session, SessionRegistry
from pulsechat.storage import TranscriptStore

log = logging.getLogger(__name__)

HANDLERS = (
    "register",
    "join",
    "leave",
    "msg",
    "priv",
    "who",
    "history",
    "ping",
)


class ChatHandlers:
    """Bundles the registries so the server loop stays thin."""

    def __init__(
        self,
        sessions: SessionRegistry,
        rooms: RoomRegistry,
        store: TranscriptStore,
        history_limit: int = 200,
    ) -> None:
        self.sessions = sessions
        self.rooms = rooms
        self.store = store
        self.history_limit = history_limit

    def dispatch(self, session: Session, frame: dict) -> dict | None:
        """Route one validated frame; returns the reply payload."""
        kind = frame["type"]
        table = {
            "register": self.handle_register,
            "join": self.handle_join,
            "leave": self.handle_leave,
            "msg": self.handle_msg,
            "priv": self.handle_priv,
            "who": self.handle_who,
            "history": self.handle_history,
            "ping": self.handle_ping,
        }
        handler = table.get(kind)
        if handler is None:
            raise ProtocolError("unknown_type", f"no handler for {kind!r}")
        return handler(session, frame)

    # -- individual handlers -------------------------------------------------

    def handle_register(self, session: Session, frame: dict) -> dict:
        name = frame["name"]
        existing = self.sessions.by_name(name)
        if existing is not None and existing.sid != session.sid:
            raise ProtocolError("name_taken", f"name {name!r} is already online")
        session.name = name
        session.registered_at = now_ts()
        self.sessions.add(session)
        log.info("registered %s from %s", name, session.peer)
        return server_event("ok", reply_to="register", name=name)

    def handle_join(self, session: Session, frame: dict) -> dict:
        room_name = frame["room"]
        room = self.rooms.get_or_create(room_name)
        first_time = room_name not in session.rooms
        fresh_member = room.add_member(session.sid)
        if room_name not in session.rooms:
            session.rooms.add(room_name)
        if first_time or fresh_member:
            self._fanout_room(
                room_name,
                server_event("presence", event="join", room=room_name, who=session.name),
                exclude=session.sid,
            )
        return server_event("ok", reply_to="join", room=room_name, fresh=first_time)

    def handle_leave(self, session: Session, frame: dict) -> dict:
        room_name = frame["room"]
        room = self.rooms.get(room_name)
        if room is None or not session.joined(room_name):
            raise ProtocolError("not_in_room", f"you are not in {room_name!r}")
        room.remove_member(session.sid)
        session.rooms.discard(room_name)
        self.rooms.drop_if_empty(room_name)
        self._fanout_room(
            room_name,
            server_event("presence", event="leave", room=room_name, who=session.name),
        )
        return server_event("ok", reply_to="leave", room=room_name)

    def handle_msg(self, session: Session, frame: dict) -> dict:
        room_name = frame["room"]
        if not session.joined(room_name):
            raise ProtocolError("not_in_room", f"join {room_name!r} before posting")
        entry = {
            "id": make_id(),
            "room": room_name,
            "from": session.name,
            "text": frame["text"],
            "ts": now_ts(),
        }
        room = self.rooms.get_or_create(room_name)
        room.append_history(entry, self.history_limit)
        self.store.append(entry)
        self._fanout_room(
            room_name,
            server_event(
                "msg",
                room=room_name,
                id=entry["id"],
                **{"from": entry["from"]},
                text=entry["text"],
            ),
        )
        return server_event("ok", reply_to="msg", room=room_name, id=entry["id"])

    def handle_priv(self, session: Session, frame: dict) -> dict:
        target = self.sessions.by_name(frame["to"])
        if target is None:
            raise ProtocolError("no_such_user", f"{frame['to']!r} is not online")
        if target.sid == session.sid:
            raise ProtocolError("self_priv", "sending a private message to yourself?")
        target.writer.write(
            encode_frame(
                server_event(
                    "priv",
                    **{"from": session.name},
                    text=frame["text"],
                    id=make_id(),
                )
            )
        )
        return server_event("ok", reply_to="priv", to=frame["to"])

    def handle_who(self, session: Session, frame: dict) -> dict:
        room_name = frame["room"]
        room = self.rooms.get(room_name)
        if room is None:
            raise ProtocolError("no_such_room", f"no room called {room_name!r}")
        names = []
        for sid in sorted(room.members):
            member = self.sessions.get(sid)
            if member is not None:
                names.append(member.name)
        return server_event("roster", room=room_name, members=names)

    def handle_history(self, session: Session, frame: dict) -> dict:
        room_name = frame["room"]
        room = self.rooms.get(room_name)
        if room is None:
            raise ProtocolError("no_such_room", f"no room called {room_name!r}")
        limit = frame.get("limit", 50)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            limit = 50
        limit = min(limit, self.history_limit)
        return server_event("history", room=room_name, messages=room.history[-limit:])

    def handle_ping(self, session: Session, frame: dict) -> dict:
        return server_event("pong")

    # -- fanout --------------------------------------------------------------

    def _fanout_room(self, room_name: str, event: dict, exclude: str | None = None) -> None:
        room = self.rooms.get(room_name)
        if room is None:
            return
        payload = encode_frame(event)
        for sid in list(room.members):
            if sid == exclude:
                continue
            member = self.sessions.get(sid)
            if member is not None:
                member.writer.write(payload)

    def _fanout_all(self, event: dict) -> None:
        payload = encode_frame(event)
        for member in self.sessions.all_sessions():
            member.writer.write(payload)

















































































