from pulsechat.rooms import Room, RoomRegistry


class TestRoom:
    def test_add_and_remove(self):
        room = Room(name="general")
        assert room.add_member("s1") is True
        assert room.add_member("s1") is False  # already in
        assert room.remove_member("s1") is True
        assert room.remove_member("s1") is False

    def test_history_trim(self):
        room = Room(name="general")
        for i in range(10):
            room.append_history({"i": i}, limit=5)
        assert [e["i"] for e in room.history] == [5, 6, 7, 8, 9]


class TestRoomRegistry:
    def test_get_or_create_is_stable(self):
        reg = RoomRegistry()
        a = reg.get_or_create("general")
        b = reg.get_or_create("general")
        assert a is b

    def test_drop_if_empty_keeps_populated_rooms(self):
        reg = RoomRegistry()
        room = reg.get_or_create("general")
        room.add_member("s1")
        reg.drop_if_empty("general")
        assert "general" in reg
        room.remove_member("s1")
        reg.drop_if_empty("general")
        assert "general" not in reg

    def test_names_sorted(self):
        reg = RoomRegistry()
        reg.get_or_create("zeta")
        reg.get_or_create("alpha")
        assert reg.names() == ["alpha", "zeta"]

    def test_total_members(self):
        reg = RoomRegistry()
        a = reg.get_or_create("a")
        b = reg.get_or_create("b")
        a.add_member("s1")
        b.add_member("s1")
        b.add_member("s2")
        assert reg.total_members() == 3

    def test_len_and_iter(self):
        reg = RoomRegistry()
        reg.get_or_create("x")
        reg.get_or_create("y")
        assert len(reg) == 2
        assert list(reg) == ["x", "y"]





















































