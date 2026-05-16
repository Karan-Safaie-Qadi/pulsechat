from pulsechat.config import Settings, load_settings


class TestLoadSettings:
    def test_defaults(self, monkeypatch):
        for var in (
            "PULSECHAT_HOST",
            "PULSECHAT_PORT",
            "PULSECHAT_DATA_DIR",
            "PULSECHAT_LOG_LEVEL",
            "PULSECHAT_BOT_RATE",
        ):
            monkeypatch.delenv(var, raising=False)
        s = load_settings()
        assert s.host == "127.0.0.1"
        assert s.port == 7788
        assert s.bot_rate == "normal"

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("PULSECHAT_HOST", "0.0.0.0")
        monkeypatch.setenv("PULSECHAT_PORT", "9001")
        monkeypatch.setenv("PULSECHAT_BOT_RATE", "FAST")
        s = load_settings()
        assert s.host == "0.0.0.0"
        assert s.port == 9001
        assert s.bot_rate == "fast"

    def test_bad_port_falls_back(self, monkeypatch):
        monkeypatch.setenv("PULSECHAT_PORT", "not-a-number")
        s = load_settings()
        assert s.port == 7788

    def test_bad_bot_rate_falls_back(self, monkeypatch):
        monkeypatch.setenv("PULSECHAT_BOT_RATE", "turbo")
        s = load_settings()
        assert s.bot_rate == "normal"

    def test_settings_frozen(self):
        s = Settings()
        try:
            s.port = 1234
        except Exception:
            pass
        else:
            raise AssertionError("Settings should be frozen")

















