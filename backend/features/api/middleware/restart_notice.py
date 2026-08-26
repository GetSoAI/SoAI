"""SoAI - API restart notice middleware [backend/features/api/middleware/restart_notice.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

__all__ = ("RestartNoticeMiddleware",)


class RestartNoticeMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)

        async def send_wrapper(message: Message) -> None:
            if message.get("type") == "http.response.start":
                try:
                    restart_required = bool(request.state.restart_required)
                except AttributeError:
                    restart_required = False
                if restart_required:
                    headers = MutableHeaders(scope=message)
                    if headers.get("X-SoAI-Restart-Required") is None:
                        headers["X-SoAI-Restart-Required"] = "true"
            await send(message)

        await self.app(scope, receive, send_wrapper)
