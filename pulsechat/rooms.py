"""Room registry.

Each room holds a set of session ids plus a bounded rolling history. The
registry is guarded by an RLock so it can be probed from other threads (the
bot engine runs its own loop in tests), while normal operation is single
event-loop.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Room:
    name: str
    members: set[str] = field(default_factory=set)
    history: list[dict] = field(default_factory=list)
    created_at: float = 0.0

    def add_member(self, sid: str) -> bool:
        """Add a member; returns True if this is a fresh join."""
        if sid in self.members:
            return False
        self.members.add(sid)
        return True

    def remove_member(self, sid: str) -> bool:
        """Remove a member; returns True if they were actually in it."""
        if sid not in self.members:
            return False
        self.members.discard(sid)
        return True

    def append_history(self, entry: dict, limit: int) -> None:
        self.history.append(entry)
        if len(self.history) > limit:
            del self.history[: len(self.history) - limit]


class RoomRegistry:
    """Thread-safe mapping of room name -> Room."""

    def __init__(self, history_limit: int = 200) -> None:
        self._lock = threading.RLock()
        self._rooms: dict[str, Room] = {}
        self._history_limit = history_limit

    def get(self, name: str) -> Room | None:
        with self._lock:
            return self._rooms.get(name)

    def get_or_create(self, name: str) -> Room:
        with self._lock:
            room = self._rooms.get(name)
            if room is None:
                room = Room(name=name, created_at=time.time())
                self._rooms[name] = room
            return room

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._rooms)

    def count(self) -> int:
        with self._lock:
            return len(self._rooms)

    def drop_if_empty(self, name: str) -> None:
        """Remove a room only when it has no members left."""
        with self._lock:
            room = self._rooms.get(name)
            if room is not None and not room.members:
                del self._rooms[name]

    def total_members(self) -> int:
        with self._lock:
            return sum(len(r.members) for r in self._rooms.values())

    def __iter__(self) -> Iterator[str]:
        return iter(self.names())

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None
















































