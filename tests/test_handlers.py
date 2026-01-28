import pytest

from pulsechat.handlers import ChatHandlers
from pulsechat.protocol import ProtocolError
from pulsechat.rooms import RoomRegistry
from pulsechat.sessions import Session, SessionRegistry
from pulsechat.storage import TranscriptStore


class FakeWriter:
    """Captures outbound frames instead of touching a socket."""

    def __init__(self):
        self.frames = []
        self.peername = ("127.0.0.1", 50000)

    def get_extra_info(self, name):
        if name == "peername":
            return self.peername
        return None

    def write(self, data):
        self.frames.append(data)


class FakeStore(TranscriptStore):
    """Transcript store that never touches disk."""

    def __init__(self):
        self.entries = []
        self.root = None

    def append(self, entry):
        self.entries.append(entry)


@pytest.fixture
def world():
    sessions = SessionRegistry()
    rooms = RoomRegistry()
    store = FakeStore()
    handlers = ChatHandlers(sessions=sessions, rooms=rooms, store=store, history_limit=100)

    def connect(name):
        writer = FakeWriter()
        session = Session(sid=name + "-sid", name=name, writer=writer)
        sessions.add(session)
        return session

    return handlers, connect


class TestRegister:
    def test_ok(self, world):
        handlers, connect = world
        s = connect("sara")
        reply = handlers.dispatch(s, {"type": "register", "name": "sara"})
        assert reply["type"] == "ok"

    def test_name_taken(self, world):
        handlers, connect = world
        connect("ali")
        s2 = connect("ali2")
        with pytest.raises(ProtocolError) as exc:
            handlers.dispatch(s2, {"type": "register", "name": "ali"})
        assert exc.value.code == "name_taken"


class TestJoinLeave:
    def test_join_then_presence_fanout(self, world):
        handlers, connect = world
        a = connect("a")
        b = connect("b")
        handlers.dispatch(a, {"type": "join", "room": "general"})
        handlers.dispatch(b, {"type": "join", "room": "general"})
        # a should have seen b's join presence
        assert any(b'"presence"' in f for f in a.writer.frames)

    def test_leave_requires_membership(self, world):
        handlers, connect = world
        s = connect("a")
        with pytest.raises(ProtocolError) as exc:
            handlers.dispatch(s, {"type": "leave", "room": "general"})
        assert exc.value.code == "not_in_room"

    def test_msg_requires_membership(self, world):
        handlers, connect = world
        s = connect("a")
        with pytest.raises(ProtocolError) as exc:
            handlers.dispatch(s, {"type": "msg", "room": "general", "text": "hi"})
        assert exc.value.code == "not_in_room"


class TestMessaging:
    def test_msg_fans_out_and_stores(self, world):
        handlers, connect = world
        a = connect("a")
        b = connect("b")
        for s in (a, b):
            handlers.dispatch(s, {"type": "join", "room": "general"})
        a.writer.frames.clear()
        handlers.dispatch(a, {"type": "msg", "room": "general", "text": "salam"})
        assert b.writer.frames, "b should receive the message"
        assert len(store_entries(handlers)) == 1

    def test_msg_goes_to_history(self, world):
        handlers, connect = world
        a = connect("a")
        handlers.dispatch(a, {"type": "join", "room": "general"})
        handlers.dispatch(a, {"type": "msg", "room": "general", "text": "one"})
        reply = handlers.dispatch(a, {"type": "history", "room": "general"})
        assert reply["messages"][0]["text"] == "one"

    def test_priv_delivers(self, world):
        handlers, connect = world
        a = connect("a")
        b = connect("b")
        handlers.dispatch(a, {"type": "priv", "to": "b", "text": "psst"})
        assert any(b'"priv"' in f for f in b.writer.frames)

    def test_priv_unknown_target(self, world):
        handlers, connect = world
        a = connect("a")
        with pytest.raises(ProtocolError) as exc:
            handlers.dispatch(a, {"type": "priv", "to": "ghost", "text": "yo"})
        assert exc.value.code == "no_such_user"

    def test_priv_to_self(self, world):
        handlers, connect = world
        a = connect("a")
        with pytest.raises(ProtocolError) as exc:
            handlers.dispatch(a, {"type": "priv", "to": "a", "text": "echo"})
        assert exc.value.code == "self_priv"


class TestRoster:
    def test_who_lists_members(self, world):
        handlers, connect = world
        a = connect("a")
        b = connect("b")
        for s in (a, b):
            handlers.dispatch(s, {"type": "join", "room": "general"})
        reply = handlers.dispatch(a, {"type": "who", "room": "general"})
        assert reply["members"] == ["a", "b"]

    def test_who_unknown_room(self, world):
        handlers, connect = world
        a = connect("a")
        with pytest.raises(ProtocolError) as exc:
            handlers.dispatch(a, {"type": "who", "room": "nope"})
        assert exc.value.code == "no_such_room"

    def test_ping(self, world):
        handlers, connect = world
        a = connect("a")
        assert handlers.dispatch(a, {"type": "ping"})["type"] == "pong"


def store_entries(handlers):
    return handlers.store.entries





























































