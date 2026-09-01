from obs_chat_control.core import (
    StreamStatus,
    format_status,
    is_authorized,
    resolve_scene,
    select_media_path,
    stream_status_from_obs,
)


def test_authorization_uses_immutable_user_ids() -> None:
    allowed = frozenset({"123", "456"})
    assert is_authorized(123, allowed)
    assert not is_authorized("streamer-name", allowed)
    assert not is_authorized(None, allowed)


def test_scene_resolution_is_case_insensitive_but_allow_listed() -> None:
    scenes = ("Starting Soon", "IRL", "BRB")
    assert resolve_scene("  irl ", scenes) == "IRL"
    assert resolve_scene("Admin", scenes) is None
    assert resolve_scene("IRL\nStopStream", scenes) is None


def test_selects_only_the_expected_ready_media_path() -> None:
    payload = {
        "items": [
            {"name": "other", "ready": True},
            {"name": "mobile", "ready": False},
        ]
    }
    assert select_media_path(payload, "mobile") is None
    payload["items"][1]["ready"] = True
    assert select_media_path(payload, "mobile") == {"name": "mobile", "ready": True}


def test_formats_live_stream_status() -> None:
    response = {
        "outputActive": True,
        "outputBytes": 730_250_000,
        "outputDuration": 1_000_000,
        "outputSkippedFrames": 3,
    }
    status = stream_status_from_obs(True, response)
    assert status.bitrate_kbps == 5_842
    assert format_status(status) == "Source: ready · OBS: live · 5842 kbps · dropped: 3"


def test_formats_unavailable_obs() -> None:
    assert format_status(StreamStatus(False, False)) == "Source: offline · OBS: unavailable"
    assert format_status(StreamStatus(None, False)) == "Source: not configured · OBS: unavailable"
