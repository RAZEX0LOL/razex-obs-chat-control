from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StreamStatus:
    source_ready: bool | None
    obs_reachable: bool
    output_active: bool = False
    bitrate_kbps: int = 0
    dropped_frames: int = 0


def is_authorized(user_id: str | int | None, allowed_user_ids: frozenset[str]) -> bool:
    return user_id is not None and str(user_id) in allowed_user_ids


def resolve_scene(requested: str, allowed_scenes: Sequence[str]) -> str | None:
    normalized = requested.strip().casefold()
    if not normalized or len(requested) > 64 or any(char in requested for char in "\r\n\0"):
        return None
    return next((scene for scene in allowed_scenes if scene.casefold() == normalized), None)


def select_media_path(payload: Mapping[str, Any], expected_path: str) -> Mapping[str, Any] | None:
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    for item in items:
        is_expected = isinstance(item, dict) and item.get("name") == expected_path
        if is_expected and item.get("ready") is True:
            return item
    return None


def stream_status_from_obs(
    source_ready: bool | None,
    response: Mapping[str, Any] | None,
) -> StreamStatus:
    if response is None:
        return StreamStatus(source_ready=source_ready, obs_reachable=False)
    duration_ms = max(int(response.get("outputDuration", 0) or 0), 1)
    output_bytes = max(int(response.get("outputBytes", 0) or 0), 0)
    bitrate_kbps = round(output_bytes * 8 / duration_ms)
    return StreamStatus(
        source_ready=source_ready,
        obs_reachable=True,
        output_active=bool(response.get("outputActive")),
        bitrate_kbps=bitrate_kbps,
        dropped_frames=max(int(response.get("outputSkippedFrames", 0) or 0), 0),
    )


def format_status(status: StreamStatus) -> str:
    if status.source_ready is None:
        source = "not configured"
    else:
        source = "ready" if status.source_ready else "offline"
    if not status.obs_reachable:
        return f"Source: {source} · OBS: unavailable"
    obs = "live" if status.output_active else "idle"
    return (
        f"Source: {source} · OBS: {obs} · {status.bitrate_kbps} kbps · "
        f"dropped: {status.dropped_frames}"
    )
