"""A small synchronous client for PulseChat.

Handy for smoke tests, load scripts, and poking the server from a REPL.
Runs its own reader thread; callbacks fire for server-pushed events
(messages, presence, privs) while request/reply goes through call().

Example:
    with ChatClient("127.0.0.1", 7788) as c:
        c.call("register", name="mina")
        c.call("join", room="general")
        c.call("msg", room="general", text="salam")
        print(c.drain_events())
"""

from __future__ import annotations

import json
import queue
import socket
import threading
import unicodedata
from typing import Any, Callable


def split_segments(text: str) -> list[str]:
    """Split text into script runs (latin vs arabic vs cjk), for renderers."""
    if not text:
        return []
    segments: list[str] = []
    current = ""
    current_dir: str | None = None

    def script_dir(ch: str) -> str:
        name = unicodedata.name(ch, "")
        if "ARABIC" in name:
            return "rtl"
        if "CJK" in name or "HEBREW" in name:
            return "rtl"
        return "ltr"

    for ch in text:
        d = script_dir(ch)
        if current_dir is None or d == current_dir:
            current += ch
            current_dir = d
        else:
            segments.append(current)
            current = ch
            current_dir = d
    if current:
        segments.append(current)
    return segments


class ChatClient:
    """Blocking client with a background reader thread."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7788, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._rfile = None
        self._seq = 0
        self._events: queue.Queue = queue.Queue()
        self._replies: dict[int, queue.Queue] = {}
        self._lock = threading.Lock()
        self._reader: threading.Thread | None = None
        self._closed = threading.Event()
        self._on_event: Callable[[dict], None] | None = None

    # -- context management ---------------------------------------------------

    def __enter__(self) -> "ChatClient":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def connect(self) -> None:
        if self._sock is not None:
            raise RuntimeError("already connected")
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._rfile = self._sock.makefile("r", encoding="utf-8", newline="\n")
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def close(self) -> None:
        self._closed.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    # -- requests ---------------------------------------------------------

    def _encode(self, kind: str, **fields: Any) -> str:
        with self._lock:
            self._seq += 1
            seq = self._seq
        payload = {"type": kind, "seq": seq, **fields}
        return json.dumps(payload, ensure_ascii=False) + "\n"

    @staticmethod
    def _is_error(frame: dict) -> bool:
        return isinstance(frame, dict) and frame.get("type") == "error"

    def call(self, kind: str, timeout: float | None = None, **fields: Any) -> dict:
        """Send one request and wait for its reply. Raises on error replies."""
        if self._sock is None:
            raise RuntimeError("not connected")
        line = self._encode(kind, **fields)
        self._sock.sendall(line.encode("utf-8"))
        seq = json.loads(line)["seq"]
        q = self._replies.setdefault(seq, queue.Queue())
        try:
            reply = q.get(timeout=timeout or self.timeout)
        except queue.Empty:
            raise TimeoutError(f"no reply for {kind!r} within {timeout or self.timeout}s")
        finally:
            self._replies.pop(seq, None)
        if self._is_error(reply):
            raise ChatError(reply.get("code", "error"), reply.get("message", ""))
        return reply

    # -- events --------------------------------------------------------

    def drain_events(self, max_items: int = 100) -> list[dict]:
        out = []
        while len(out) < max_items:
            try:
                out.append(self._events.get_nowait())
            except queue.Empty:
                break
        return out

    def wait_event(self, kind: str, timeout: float = 3.0) -> dict | None:
        """Block until an event of `kind` arrives (or timeout)."""
        deadline = None
        buffered = []
        while True:
            try:
                ev = self._events.get(timeout=timeout)
            except queue.Empty:
                break
            if ev.get("type") == kind:
                for b in buffered:
                    self._events.put(b)
                return ev
            buffered.append(ev)
        for b in buffered:
            self._events.put(b)
        return None

    # -- reader thread -------------------------------------------------

    def _read_loop(self) -> None:
        assert self._rfile is not None
        while not self._closed.is_set():
            try:
                line = self._rfile.readline()
            except (OSError, ValueError):
                break
            if not line:
                break
            try:
                frame = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(frame, dict):
                continue
            seq = frame.get("reply_seq")
            if seq is not None and seq in self._replies:
                self._replies[seq].put(frame)
            else:
                self._events.put(frame)
                if self._on_event is not None:
                    try:
                        self._on_event(frame)
                    except Exception:
                        pass


class ChatError(RuntimeError):
    """Server rejected a request."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message

































