"""Runtime configuration, sourced from the environment.

The server is meant to run in containers and CI, so every knob here has an
environment variable twin. Nothing in this module talks to the network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable settings bundle for one server run."""

    host: str = "127.0.0.1"
    port: int = 7788
    data_dir: Path = Path("data") / "transcripts"
    log_level: str = "INFO"
    max_message_len: int = 2000
    history_limit: int = 200
    bot_rate: str = "normal"
    ping_interval: float = 30.0
    read_timeout: float = 120.0
    extra: dict = field(default_factory=dict)


def load_settings() -> Settings:
    """Build a Settings from environment variables.

    Recognized variables:
        PULSECHAT_HOST, PULSECHAT_PORT, PULSECHAT_DATA_DIR,
        PULSECHAT_LOG_LEVEL, PULSECHAT_MAX_MESSAGE_LEN,
        PULSECHAT_HISTORY_LIMIT, PULSECHAT_BOT_RATE
    """
    bot_rate = os.environ.get("PULSECHAT_BOT_RATE", "normal").strip().lower()
    if bot_rate not in ("fast", "normal", "slow"):
        bot_rate = "normal"

    return Settings(
        host=os.environ.get("PULSECHAT_HOST", "127.0.0.1"),
        port=_int_env("PULSECHAT_PORT", 7788),
        data_dir=Path(os.environ.get("PULSECHAT_DATA_DIR", "data/transcripts")),
        log_level=os.environ.get("PULSECHAT_LOG_LEVEL", "INFO").upper(),
        max_message_len=_int_env("PULSECHAT_MAX_MESSAGE_LEN", 2000),
        history_limit=_int_env("PULSECHAT_HISTORY_LIMIT", 200),
        bot_rate=bot_rate,
    )



















































