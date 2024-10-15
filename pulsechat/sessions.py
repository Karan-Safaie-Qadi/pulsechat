"""Per-connection session state.

A session is one authenticated client connection: its id, display name, the
rooms it has joined, and a writer handle used to push server events back.
The registry is the single source of truth for "who is online", which lets
handlers and the bot engine look up targets by name without touching sockets.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field


@dataclass
class Session:
    sid: str
    name: str
    writer: asyncio.StreamWriter
    rooms: set[str] = field(default_factory=set)
    registered_at: float = 0.0

    @property
    def peer(self) -> str:
        peername = self.writer.get_extra_info("peername")
        if not peername:
            return "unknown"
        host, port = peername[0], peername[1]
        return f"{host}:{port}"

    def joined(self, room: str) -> bool:
        return room in self.rooms


class SessionRegistry:
    """Thread-safe registry of live sessions, indexed by id and by name."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._by_sid: dict[str, Session] = {}
        self._by_name: dict[str, Session] = {}

    def add(self, session: Session) -> bool:
        """Register a session. Names are unique; returns False on collision."""
        with self._lock:
            if session.name in self._by_name:
                return False
            self._by_sid[session.sid] = session
            self._by_name[session.name] = session
            return True

    def remove(self, sid: str) -> Session | None:
        with self._lock:
            session = self._by_sid.pop(sid, None)
            if session is not None:
                if self._by_name.get(session.name) is session:
                    del self._by_name[session.name]
            return session

    def get(self, sid: str) -> Session | None:
        with self._lock:
            return self._by_sid.get(sid)

    def by_name(self, name: str) -> Session | None:
        with self._lock:
            return self._by_name.get(name)

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._by_name)

    def count(self) -> int:
        with self._lock:
            return len(self._by_sid)

    def all_sessions(self) -> list[Session]:
        with self._lock:
            return list(self._by_sid.values())
