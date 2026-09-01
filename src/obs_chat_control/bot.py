from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import asqlite
import twitchio
from twitchio import eventsub
from twitchio.ext import commands

from .config import Settings
from .core import format_status, is_authorized, resolve_scene, stream_status_from_obs
from .integrations import MediaMtxClient, ObsController

if TYPE_CHECKING:
    from collections.abc import Sequence

LOGGER = logging.getLogger(__name__)


class ObsCommands(commands.Component):
    def __init__(self, settings: Settings, obs: ObsController, mediamtx: MediaMtxClient) -> None:
        self._settings = settings
        self._obs = obs
        self._mediamtx = mediamtx

    def _authorized(self, ctx: commands.Context) -> bool:
        return is_authorized(ctx.chatter.id, self._settings.twitch.allowed_user_ids)

    @commands.command(name="start")
    async def start_stream(self, ctx: commands.Context) -> None:
        if not self._authorized(ctx):
            return
        response = await self._obs.call("StartStream")
        message = "Stream started." if response is not None else "OBS unavailable or already live."
        await ctx.send(message)

    @commands.command(name="stop")
    async def stop_stream(self, ctx: commands.Context) -> None:
        if not self._authorized(ctx):
            return
        response = await self._obs.call("StopStream")
        message = "Stream stopped." if response is not None else "OBS unavailable or already idle."
        await ctx.send(message)

    @commands.command(name="status")
    async def status(self, ctx: commands.Context) -> None:
        if not self._authorized(ctx):
            return
        source_task = asyncio.create_task(self._mediamtx.is_ready())
        obs_task = asyncio.create_task(self._obs.call("GetStreamStatus"))
        source_ready, obs_response = await asyncio.gather(source_task, obs_task)
        await ctx.send(format_status(stream_status_from_obs(source_ready, obs_response)))

    @commands.command(name="scene")
    async def scene(self, ctx: commands.Context, *, name: str = "") -> None:
        if not self._authorized(ctx):
            return
        scene = resolve_scene(name, self._settings.obs.allowed_scenes)
        if scene is None:
            await ctx.send("Scene is not in the configured allow-list.")
            return
        response = await self._obs.call("SetCurrentProgramScene", {"sceneName": scene})
        await ctx.send(f"Scene changed to {scene}." if response is not None else "OBS unavailable.")


class Bot(commands.AutoBot):
    def __init__(
        self,
        settings: Settings,
        token_database: asqlite.Pool,
        subscriptions: list[eventsub.SubscriptionPayload],
    ) -> None:
        self._settings = settings
        self._token_database = token_database
        self._obs = ObsController(settings.obs)
        self._mediamtx = MediaMtxClient(settings.mediamtx)
        super().__init__(
            client_id=settings.twitch.client_id,
            client_secret=settings.twitch.client_secret,
            bot_id=settings.twitch.bot_id,
            owner_id=settings.twitch.owner_id,
            prefix="!",
            subscriptions=subscriptions,
            force_subscribe=True,
        )

    async def setup_hook(self) -> None:
        await self.add_component(ObsCommands(self._settings, self._obs, self._mediamtx))

    async def event_oauth_authorized(
        self,
        payload: twitchio.authentication.UserTokenPayload,
    ) -> None:
        await self.add_token(payload.access_token, payload.refresh_token)
        if payload.user_id == self.bot_id or payload.user_id is None:
            return
        subscriptions = [
            eventsub.ChatMessageSubscription(
                broadcaster_user_id=payload.user_id,
                user_id=self.bot_id,
            )
        ]
        result = await self.multi_subscribe(subscriptions)
        if result.errors:
            LOGGER.warning(
                "EventSub subscription errors for %s: %r",
                payload.user_id,
                result.errors,
            )

    async def add_token(
        self,
        token: str,
        refresh: str,
    ) -> twitchio.authentication.ValidateTokenPayload:
        payload = await super().add_token(token, refresh)
        query = """
            INSERT INTO tokens (user_id, access_token, refresh_token)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token
        """
        async with self._token_database.acquire() as connection:
            await connection.execute(query, (payload.user_id, token, refresh))
            await connection.commit()
        return payload

    async def close(self, **kwargs: object) -> None:
        await self._obs.close()
        await super().close(**kwargs)


async def prepare_database(
    database: asqlite.Pool,
    bot_id: str,
) -> tuple[list[tuple[str, str]], list[eventsub.SubscriptionPayload]]:
    async with database.acquire() as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tokens (
                user_id TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL
            )
            """
        )
        await connection.commit()
        rows: Sequence[sqlite3.Row] = await connection.fetchall(
            "SELECT user_id, access_token, refresh_token FROM tokens"
        )
    tokens = [(row["access_token"], row["refresh_token"]) for row in rows]
    subscriptions = [
        eventsub.ChatMessageSubscription(broadcaster_user_id=row["user_id"], user_id=bot_id)
        for row in rows
        if row["user_id"] != bot_id
    ]
    return tokens, subscriptions


async def run_bot(settings: Settings, database_path: Path) -> None:
    database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    async with asqlite.create_pool(database_path) as database:
        os.chmod(database_path, 0o600)
        tokens, subscriptions = await prepare_database(database, settings.twitch.bot_id)
        async with Bot(settings, database, subscriptions) as bot:
            for token, refresh in tokens:
                await bot.add_token(token, refresh)
            await bot.start(load_tokens=False)
