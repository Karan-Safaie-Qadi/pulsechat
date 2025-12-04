import json

import pytest

from pulsechat.client import ChatClient


class TestSplitSegments:
    def test_ascii(self):
        from pulsechat.client import split_segments

        assert split_segments("hello world") == ["hello world"]

    def test_mixed_scripts(self):
        from pulsechat.client import split_segments

        segs = split_segments("hello سلام world")
        assert segs == ["hello ", "سلام", " world"]

    def test_empty(self):
        from pulsechat.client import split_segments

        assert split_segments("") == []


class TestChatClientUnit:
    """Socket-free checks of framing behavior."""

    def test_encode_request_has_seq(self):
        import threading

        c = ChatClient.__new__(ChatClient)
        c._seq = 0
        c._lock = threading.Lock()

        line = ChatClient._encode(c, "ping")
        payload = json.loads(line)
        assert payload["seq"] == 1
        assert payload["type"] == "ping"

    def test_error_detection(self):
        c = ChatClient.__new__(ChatClient)
        assert ChatClient._is_error({"type": "error"}) is True
        assert ChatClient._is_error({"type": "ok"}) is False





















































