import json

import pytest

from pulsechat.protocol import (
    ProtocolError,
    encode_frame,
    parse_frame,
    sanitize_text,
    validate,
)


class TestValidate:
    def test_register_ok(self):
        frame = validate("register", {"name": "  sara "})
        assert frame["name"] == "sara"

    def test_register_strips_control_chars(self):
        frame = validate("register", {"name": "sa\tra"})
        assert "\t" not in frame["name"]

    def test_register_empty_name_rejected(self):
        with pytest.raises(ProtocolError) as exc:
            validate("register", {"name": "   "})
        assert exc.value.code == "bad_name"

    def test_register_long_name_clamped(self):
        frame = validate("register", {"name": "x" * 100})
        assert len(frame["name"]) == 32

    def test_unknown_type(self):
        with pytest.raises(ProtocolError) as exc:
            validate("explode", {})
        assert exc.value.code == "unknown_type"

    def test_missing_field(self):
        with pytest.raises(ProtocolError) as exc:
            validate("msg", {"room": "general"})
        assert exc.value.code == "missing_field"

    def test_msg_text_clamped(self):
        frame = validate("msg", {"room": "r", "text": "y" * 5000}, max_text=100)
        assert len(frame["text"]) == 100

    def test_join_bad_room(self):
        with pytest.raises(ProtocolError) as exc:
            validate("join", {"room": ""})
        assert exc.value.code == "bad_room"

    def test_ping_has_no_fields(self):
        frame = validate("ping", {})
        assert frame == {"type": "ping"}


class TestParseFrame:
    def test_roundtrip(self):
        frame = parse_frame(json.dumps({"type": "msg", "room": "general", "text": "hi"}))
        assert frame["room"] == "general"
        assert frame["text"] == "hi"

    def test_bad_json(self):
        with pytest.raises(ProtocolError) as exc:
            parse_frame("{not json")
        assert exc.value.code == "bad_json"

    def test_non_object(self):
        with pytest.raises(ProtocolError) as exc:
            parse_frame("[1, 2, 3]")
        assert exc.value.code == "bad_frame"

    def test_frame_too_large(self):
        big = json.dumps({"type": "msg", "room": "r", "text": "a" * 20000})
        with pytest.raises(ProtocolError) as exc:
            parse_frame(big)
        assert exc.value.code == "frame_too_large"

    def test_encode_frame_unicode(self):
        data = encode_frame({"text": "سلام"})
        assert "سلام".encode() in data
        assert data.endswith(b"\n")


def test_sanitize_keeps_newline_only():
    text = sanitize_text("line1\nline2\x00\x1f")
    assert text == "line1\nline2"
