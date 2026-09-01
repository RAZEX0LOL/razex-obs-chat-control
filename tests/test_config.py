from pathlib import Path

import pytest

from obs_chat_control.config import ConfigError, load_settings

VALID_CONFIG = """
[twitch]
client_id = "client-id"
client_secret = "client-secret"
bot_id = "123"
owner_id = "456"
allowed_user_ids = ["456", "789"]

[obs]
host = "127.0.0.1"
port = 4455
password = "long-obs-password"
allowed_scenes = ["Starting Soon", "IRL"]

[mediamtx]
api_url = "http://127.0.0.1:9997"
path = "mobile"
"""


def write_config(tmp_path: Path, content: str = VALID_CONFIG) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(content)
    return path


def test_loads_valid_settings(tmp_path: Path) -> None:
    settings = load_settings(write_config(tmp_path))
    assert settings.obs.websocket_url == "ws://127.0.0.1:4455"
    assert settings.twitch.allowed_user_ids == frozenset({"456", "789"})
    assert settings.mediamtx.path == "mobile"


@pytest.mark.parametrize(
    ("before", "after", "message"),
    [
        ('client_secret = "client-secret"', 'client_secret = "REPLACE_ME"', "client_secret"),
        ('bot_id = "123"', 'bot_id = "bot-name"', "numeric Twitch user ID"),
        ('host = "127.0.0.1"', 'host = "0.0.0.0"', "unspecified address"),
        ('password = "long-obs-password"', 'password = "short"', "at least 12"),
        (
            'api_url = "http://127.0.0.1:9997"',
            'api_url = "http://example.com:9997"',
            "only for local or private",
        ),
    ],
)
def test_rejects_unsafe_values(tmp_path: Path, before: str, after: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_settings(write_config(tmp_path, VALID_CONFIG.replace(before, after)))


def test_allows_disabling_mediamtx(tmp_path: Path) -> None:
    content = VALID_CONFIG.replace('api_url = "http://127.0.0.1:9997"', 'api_url = ""').replace(
        'path = "mobile"', 'path = ""'
    )
    assert load_settings(write_config(tmp_path, content)).mediamtx.api_url is None
