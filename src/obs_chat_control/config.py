from __future__ import annotations

import ipaddress
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ConfigError(ValueError):
    """Raised when a configuration value is missing or unsafe."""


@dataclass(frozen=True, slots=True)
class TwitchSettings:
    client_id: str
    client_secret: str
    bot_id: str
    owner_id: str
    allowed_user_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class ObsSettings:
    host: str
    port: int
    password: str
    allowed_scenes: tuple[str, ...]

    @property
    def websocket_url(self) -> str:
        return f"ws://{self.host}:{self.port}"


@dataclass(frozen=True, slots=True)
class MediaMtxSettings:
    api_url: str | None
    path: str | None


@dataclass(frozen=True, slots=True)
class Settings:
    twitch: TwitchSettings
    obs: ObsSettings
    mediamtx: MediaMtxSettings


def _required_text(section: dict[str, object], key: str) -> str:
    value = str(section.get(key, "")).strip()
    if not value or "REPLACE_ME" in value:
        raise ConfigError(f"{key} must be configured")
    return value


def _user_id(section: dict[str, object], key: str) -> str:
    value = _required_text(section, key)
    if not value.isascii() or not value.isdigit():
        raise ConfigError(f"{key} must be a numeric Twitch user ID")
    return value


def _safe_host(value: str) -> str:
    if "://" in value or any(character.isspace() for character in value):
        raise ConfigError("obs.host must be a hostname or IP address without a scheme")
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return value
    if address.is_unspecified:
        raise ConfigError("obs.host cannot be an unspecified address")
    return value


def _media_url(value: object) -> str | None:
    url = str(value or "").strip().rstrip("/")
    if not url:
        return None
    parsed = urlparse(url)
    has_valid_origin = (
        parsed.scheme in {"http", "https"}
        and parsed.hostname is not None
        and parsed.path in {"", "/"}
    )
    if not has_valid_origin:
        raise ConfigError("mediamtx.api_url must be an HTTP(S) origin without a path")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigError("mediamtx.api_url cannot include credentials, query, or fragment")
    if parsed.scheme == "http":
        try:
            is_private = ipaddress.ip_address(parsed.hostname).is_private
        except ValueError:
            is_private = parsed.hostname in {"localhost"} or parsed.hostname.endswith(".local")
        if not is_private:
            raise ConfigError("plain HTTP is allowed only for local or private mediamtx addresses")
    return url


def load_settings(path: Path) -> Settings:
    try:
        with path.open("rb") as config_file:
            raw = tomllib.load(config_file)
    except FileNotFoundError as error:
        raise ConfigError(f"configuration file not found: {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"invalid TOML in {path}: {error}") from error

    twitch = raw.get("twitch", {})
    obs = raw.get("obs", {})
    mediamtx = raw.get("mediamtx", {})
    if not isinstance(twitch, dict) or not isinstance(obs, dict) or not isinstance(mediamtx, dict):
        raise ConfigError("twitch, obs, and mediamtx must be TOML tables")

    allowed_values = twitch.get("allowed_user_ids", [])
    if not isinstance(allowed_values, list) or not allowed_values:
        raise ConfigError("twitch.allowed_user_ids must contain at least one user ID")
    allowed_user_ids = frozenset(str(value).strip() for value in allowed_values)
    if any(not value.isascii() or not value.isdigit() for value in allowed_user_ids):
        raise ConfigError("twitch.allowed_user_ids must contain only numeric Twitch user IDs")

    port = obs.get("port")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ConfigError("obs.port must be an integer between 1 and 65535")

    password = _required_text(obs, "password")
    if len(password) < 12:
        raise ConfigError("obs.password must be at least 12 characters")

    scene_values = obs.get("allowed_scenes", [])
    if not isinstance(scene_values, list) or not scene_values:
        raise ConfigError("obs.allowed_scenes must contain at least one scene")
    allowed_scenes = tuple(str(scene).strip() for scene in scene_values)
    invalid_scene = any(
        not scene or len(scene) > 64 or any(char in scene for char in "\r\n\0")
        for scene in allowed_scenes
    )
    if invalid_scene:
        raise ConfigError("every allowed OBS scene must be 1-64 printable characters")

    media_url = _media_url(mediamtx.get("api_url"))
    media_path = str(mediamtx.get("path", "")).strip() or None
    if bool(media_url) != bool(media_path):
        raise ConfigError("mediamtx.api_url and mediamtx.path must be configured together")

    return Settings(
        twitch=TwitchSettings(
            client_id=_required_text(twitch, "client_id"),
            client_secret=_required_text(twitch, "client_secret"),
            bot_id=_user_id(twitch, "bot_id"),
            owner_id=_user_id(twitch, "owner_id"),
            allowed_user_ids=allowed_user_ids,
        ),
        obs=ObsSettings(
            host=_safe_host(_required_text(obs, "host")),
            port=port,
            password=password,
            allowed_scenes=allowed_scenes,
        ),
        mediamtx=MediaMtxSettings(api_url=media_url, path=media_path),
    )
