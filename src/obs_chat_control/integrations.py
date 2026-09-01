from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from typing import Any

import simpleobsws

from .config import MediaMtxSettings, ObsSettings
from .core import select_media_path

LOGGER = logging.getLogger(__name__)


class ObsController:
    def __init__(self, settings: ObsSettings) -> None:
        self._settings = settings
        self._client: simpleobsws.WebSocketClient | None = None
        self._lock = asyncio.Lock()

    async def _connect(self) -> simpleobsws.WebSocketClient:
        if self._client is None:
            self._client = simpleobsws.WebSocketClient(
                url=self._settings.websocket_url,
                password=self._settings.password,
            )
        if not self._client.identified:
            await asyncio.wait_for(self._client.connect(), timeout=5)
            await asyncio.wait_for(self._client.wait_until_identified(), timeout=5)
        return self._client

    async def call(
        self,
        request_type: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        async with self._lock:
            try:
                client = await self._connect()
                response = await asyncio.wait_for(
                    client.call(simpleobsws.Request(request_type, data or {})),
                    timeout=7,
                )
            except (TimeoutError, OSError, simpleobsws.NotIdentifiedError) as error:
                LOGGER.warning("OBS request %s failed: %s", request_type, error)
                self._client = None
                return None
        if not response.ok():
            LOGGER.warning("OBS rejected %s: %s", request_type, response.requestStatus.comment)
            return None
        return response.responseData or {}

    async def close(self) -> None:
        if self._client is not None:
            await self._client.disconnect()


class MediaMtxClient:
    def __init__(self, settings: MediaMtxSettings) -> None:
        self._settings = settings

    def _fetch_sync(self) -> bool | None:
        if self._settings.api_url is None or self._settings.path is None:
            return None
        request = urllib.request.Request(  # noqa: S310 -- the origin is validated at startup
            f"{self._settings.api_url}/v3/paths/list",
            headers={"Accept": "application/json", "User-Agent": "razex-obs-chat-control/1.0"},
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 -- only validated HTTP(S) origins reach here
                request,
                timeout=2,
            ) as response:
                payload = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            LOGGER.warning("mediamtx status request failed: %s", error)
            return False
        return select_media_path(payload, self._settings.path) is not None

    async def is_ready(self) -> bool | None:
        return await asyncio.to_thread(self._fetch_sync)
