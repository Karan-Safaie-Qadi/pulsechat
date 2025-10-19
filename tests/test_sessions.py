from pulsechat.sessions import Session, SessionRegistry


class FakeWriter:
    def get_extra_info(self, name):
        if name == "peername":
            return ("127.0.0.1", 55555)
        return None


def make_session(name, sid):
    return Session(sid=sid, name=name, writer=FakeWriter())


class TestSessionRegistry:
    def test_add_and_lookup(self):
        reg = SessionRegistry()
        s = make_session("sara", "s1")
        assert reg.add(s) is True
        assert reg.get("s1") is s
        assert reg.by_name("sara") is s
        assert reg.count() == 1

    def test_duplicate_name_rejected(self):
        reg = SessionRegistry()
        assert reg.add(make_session("sara", "s1")) is True
        assert reg.add(make_session("sara", "s2")) is False

    def test_remove_unbinds_name(self):
        reg = SessionRegistry()
        s = make_session("sara", "s1")
        reg.add(s)
        removed = reg.remove("s1")
        assert removed is s
        assert reg.by_name("sara") is None
        assert reg.count() == 0

    def test_remove_unknown_sid(self):
        reg = SessionRegistry()
        assert reg.remove("ghost") is None

    def test_names_sorted(self):
        reg = SessionRegistry()
        reg.add(make_session("zahra", "s1"))
        reg.add(make_session("ali", "s2"))
        assert reg.names() == ["ali", "zahra"]

    def test_peer_formatting(self):
        s = make_session("sara", "s1")
        assert s.peer == "127.0.0.1:55555"

    def test_joined_membership(self):
        s = make_session("sara", "s1")
        s.rooms.add("general")
        assert s.joined("general") is True
        assert s.joined("random") is False
















































