import json

from pulsechat.storage import TranscriptStore


def make_entry(room, text, ts):
    return {"id": f"id-{text}", "room": room, "from": "tester", "text": text, "ts": ts}


class TestTranscriptStore:
    def test_append_writes_jsonl(self, tmp_path):
        store = TranscriptStore(tmp_path)
        store.append(make_entry("general", "hello", 1730000000.0))
        files = list(tmp_path.rglob("*.jsonl"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8").strip())
        assert data["text"] == "hello"
        store.close()

    def test_room_name_sanitized_for_fs(self, tmp_path):
        store = TranscriptStore(tmp_path)
        store.append(make_entry("weird/room name", "x", 1730000000.0))
        files = list(tmp_path.rglob("*.jsonl"))
        assert any("weird_room_name" in f.name for f in files)
        store.close()

    def test_read_room_returns_last_n(self, tmp_path):
        store = TranscriptStore(tmp_path)
        for i in range(12):
            store.append(make_entry("general", f"m{i}", 1730000000.0 + i))
        msgs = store.read_room("general", limit=5)
        assert [m["text"] for m in msgs] == ["m7", "m8", "m9", "m10", "m11"]
        store.close()

    def test_read_missing_room_is_empty(self, tmp_path):
        store = TranscriptStore(tmp_path)
        assert store.read_room("ghost") == []
        store.close()

    def test_entries_need_ts(self, tmp_path):
        store = TranscriptStore(tmp_path)
        bad = {"room": "general", "text": "x"}
        try:
            store.append(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for missing ts")
        store.close()










































































