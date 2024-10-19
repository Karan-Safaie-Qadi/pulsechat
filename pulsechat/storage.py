"""Transcript persistence.

Messages are appended to one JSONL file per room per UTC day:
``data/transcripts/<YYYY-MM-DD>/<room>.jsonl``. The directory partition makes
rotation and cleanup trivial (rm yesterday's folder in a cron job if you only
need a rolling window).

Appends happen from the event loop; the store flushes on every write because
chat traffic here is low-volume and losing messages on a crash is worse than
a few extra write() calls.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


class TranscriptStore:
    """Append-only JSONL store, partitioned by day and room."""

    def __init__(self, root: Path, flush: bool = True) -> None:
        self.root = Path(root)
        self.flush = flush
        self._lock = threading.Lock()
        self._handles: dict[str, object] = {}
        self.root.mkdir(parents=True, exist_ok=True)

    def _day_dir(self, ts: float) -> Path:
        day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        return self.root / day

    def _path_for(self, room: str, ts: float) -> Path:
        safe_room = "".join(c if c.isalnum() or c in "-_" else "_" for c in room)
        return self._day_dir(ts) / f"{safe_room}.jsonl"

    def append(self, entry: dict) -> None:
        """Append one message entry to the current day's file for its room."""
        ts = entry.get("ts")
        if ts is None:
            raise ValueError("entry must carry a ts field")
        path = self._path_for(entry["room"], ts)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            handle = self._handles.get(str(path))
            if handle is None:
                handle = open(path, "a", encoding="utf-8")
                self._handles[str(path)] = handle
            handle.write(line + "\n")
            if self.flush:
                handle.flush()

    def close(self) -> None:
        with self._lock:
            for handle in self._handles.values():
                try:
                    handle.close()
                except Exception:  # noqa: BLE001 - closing must never raise
                    pass
            self._handles.clear()

    def read_room(self, room: str, limit: int = 50) -> list[dict]:
        """Read the last `limit` messages for a room across all day dirs."""
        safe_room = "".join(c if c.isalnum() or c in "-_" else "_" for c in room)
        lines: list[str] = []
        for day_dir in sorted(self.root.iterdir()):
            path = day_dir / f"{safe_room}.jsonl"
            if path.is_file():
                with open(path, encoding="utf-8") as fh:
                    lines.extend(fh.readlines())
        out = []
        for raw in lines[-limit:]:
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                log.warning("skipping corrupt transcript line in %s", room)
        return out
