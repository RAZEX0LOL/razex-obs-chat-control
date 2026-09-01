from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

import twitchio

from .bot import run_bot
from .config import ConfigError, load_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Control OBS from an allow-listed Twitch chat.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("BOT_CONFIG", "/etc/obs-chat-control/config.toml")),
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.environ.get("BOT_DATABASE", "/var/lib/obs-chat-control/tokens.db")),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    twitchio.utils.setup_logging(level=logging.INFO)
    try:
        settings = load_settings(args.config)
        asyncio.run(run_bot(settings, args.database))
    except ConfigError as error:
        raise SystemExit(f"Configuration error: {error}") from error
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Shutting down")


if __name__ == "__main__":
    main()
