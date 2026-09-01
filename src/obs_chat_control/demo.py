from __future__ import annotations

from .core import StreamStatus, format_status, resolve_scene


def main() -> None:
    allowed_scenes = ("Starting Soon", "IRL", "BRB")
    examples = (
        ("streamer", "!status", format_status(StreamStatus(True, True, True, 5_842, 0))),
        ("streamer", "!scene IRL", f"Scene changed to {resolve_scene('IRL', allowed_scenes)}."),
        ("streamer", "!stop", "Stream stopped."),
    )
    print("Local demo — Twitch and OBS are mocked")
    for user, command, response in examples:
        print(f"{user}> {command}")
        print(f"bot> {response}")


if __name__ == "__main__":
    main()
