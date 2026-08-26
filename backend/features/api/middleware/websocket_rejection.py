"""SoAI - WebSocket middleware rejection helpers [backend/features/api/middleware/websocket_rejection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from starlette.types import Receive, Send

__all__ = ("reject_websocket_connection",)


async def reject_websocket_connection(
    receive: Receive,
    send: Send,
    *,
    code: int,
    reason: str,
) -> None:
    message = await receive()
    if message.get("type") != "websocket.connect":
        return
    await send(
        {
            "type": "websocket.close",
            "code": code,
            "reason": reason,
        },
    )
