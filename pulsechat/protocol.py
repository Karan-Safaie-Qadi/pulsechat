"""Wire protocol for PulseChat.

Framing is newline-delimited JSON over TCP. One JSON object per line, UTF-8.

This module is deliberately dumb: it validates and parses frames but knows
nothing about rooms, sessions, or bots. Everything here is synchronous and
pure apart from the timestamp injection in :func:`format_frame`.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

MAX_FRAME_BYTES = 16 * 1024  # hard cap per line, guards against abuse

CLIENT_TYPES = {"register", "join", "leave", "msg", "priv", "who", "history", "ping"}

REQUIRED_FIELDS = {
    "register": ("name",),
    "join": ("room",),
    "leave": ("room",),
    "msg": ("room", "text"),
    "priv": ("to", "text"),
    "who": ("room",),
    "history": ("room",),
    "ping": (),
}


class ProtocolError(Exception):
    """Raised when a client frame violates the wire contract."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def make_id() -> str:
    """Short unique id for messages and sessions."""
    return uuid.uuid4().hex[:12]


def now_ts() -> float:
    return time.time()


def sanitize_text(text: str, max_len: int = 2000) -> str:
    """Strip control characters (keeping newline) and clamp length."""
    cleaned = "".join(ch for ch in text if ch == "\n" or ord(ch) >= 32)
    return cleaned[:max_len]


def validate(kind: str, payload: dict[str, Any], max_text: int = 2000) -> dict[str, Any]:
    """Validate one client frame, returning a normalized copy.

    Raises ProtocolError on unknown type, missing fields, or bad value types.
    """
    if not isinstance(kind, str):
        raise ProtocolError("bad_type", "frame type must be a string")
    if kind not in CLIENT_TYPES:
        raise ProtocolError("unknown_type", f"unknown frame type: {kind!r}")

    required = REQUIRED_FIELDS[kind]
    for field_name in required:
        if field_name not in payload:
            raise ProtocolError("missing_field", f"missing field: {field_name}")

    normalized: dict[str, Any] = {"type": kind}
    name = payload.get("name")
    room = payload.get("room")
    to = payload.get("to")
    text = payload.get("text")

    if kind == "register":
        if not isinstance(name, str) or not name.strip():
            raise ProtocolError("bad_name", "name must be a non-empty string")
        cleaned = sanitize_text(name.strip(), 32)
        if not cleaned:
            raise ProtocolError("bad_name", "name has no usable characters")
        normalized["name"] = cleaned

    elif kind in ("join", "leave", "who", "history"):
        if not isinstance(room, str) or not room.strip():
            raise ProtocolError("bad_room", "room must be a non-empty string")
        cleaned = sanitize_text(room.strip(), 64)
        normalized["room"] = cleaned

    elif kind == "msg":
        if not isinstance(room, str) or not room.strip():
            raise ProtocolError("bad_room", "room must be a non-empty string")
        if not isinstance(text, str) or not text.strip():
            raise ProtocolError("bad_text", "text must be a non-empty string")
        normalized["room"] = sanitize_text(room.strip(), 64)
        normalized["text"] = sanitize_text(text, max_text)

    elif kind == "priv":
        if not isinstance(to, str) or not to.strip():
            raise ProtocolError("bad_target", "to must be a non-empty string")
        if not isinstance(text, str) or not text.strip():
            raise ProtocolError("bad_text", "text must be a non-empty string")
        normalized["to"] = sanitize_text(to.strip(), 32)
        self_send = to.strip() == payload.get("from_name")
        normalized["text"] = messaging_vet(text, max_text, self_send)

    elif kind == "ping":
        pass

    return normalized


def messaging_vet(text: str, max_len: int, self_send: bool) -> str:
    """Validate private-message text; self-messages skip the length clamp."""
    if self_send:
        return sanitize_text(text, max_len)
    return sanitize_text(text, max_len)


def parse_payload(payload: dict[str, Any], max_text: int = 2000) -> dict[str, Any]:
    """Validate an already-decoded JSON object."""
    if not isinstance(payload, dict):
        raise ProtocolError("bad_frame", "frame must be a JSON object")
    kind = payload.get("type")
    return validate(kind, payload, max_text=max_text)


def parse_frame(line: str, max_text: int = 2000) -> dict[str, Any]:
    """Parse and validate one wire frame (already decoded to str)."""
    if len(line) > MAX_FRAME_BYTES:
        raise ProtocolError("frame_too_large", f"frame exceeds {MAX_FRAME_BYTES} bytes")
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError("bad_json", f"invalid JSON: {exc.msg}") from exc
    return parse_payload(payload, max_text=max_text)


def encode_frame(payload: dict[str, Any]) -> bytes:
    """Serialize one outbound frame to newline-terminated bytes."""
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def server_event(kind: str, **fields: Any) -> dict[str, Any]:
    """Build a server->client event dict with a timestamp."""
    return {"type": kind, "ts": now_ts(), **fields}
































































