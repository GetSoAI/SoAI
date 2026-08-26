"""SoAI - Authoritative server-time response header middleware [backend/features/api/middleware/server_time.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.timing.epoch import epoch_ms

__all__ = ("SOAI_SERVER_TIME_HEADER_NAME", "ServerTimeMiddleware")

SOAI_SERVER_TIME_HEADER_NAME = "X-SoAI-Server-Time-Ms"


class ServerTimeMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message.get("type") == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers[SOAI_SERVER_TIME_HEADER_NAME] = str(epoch_ms())
            await send(message)

        await self.app(scope, receive, send_wrapper)
