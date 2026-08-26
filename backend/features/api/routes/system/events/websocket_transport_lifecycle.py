"""SoAI - WebSocket transport lifecycle policy [backend/features/api/routes/system/events/websocket_transport_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import Final

from fastapi import WebSocket, WebSocketDisconnect
from starlette.requests import ClientDisconnect
from starlette.websockets import WebSocketState

__all__ = (
    "WEBSOCKET_CLIENT_DISCONNECT_EXCEPTIONS",
    "WEBSOCKET_TERMINAL_LIFECYCLE_EXCEPTIONS",
    "WEBSOCKET_TRANSPORT_TERMINAL_EXCEPTIONS",
    "is_websocket_close_state_error",
    "should_close_websocket_application_state",
)

WEBSOCKET_CLIENT_DISCONNECT_EXCEPTIONS: Final[tuple[type[BaseException], ...]] = (
    WebSocketDisconnect,
    ClientDisconnect,
)

WEBSOCKET_TRANSPORT_TERMINAL_EXCEPTIONS: Final[tuple[type[BaseException], ...]] = (
    *WEBSOCKET_CLIENT_DISCONNECT_EXCEPTIONS,
    OSError,
)

WEBSOCKET_TERMINAL_LIFECYCLE_EXCEPTIONS: Final[tuple[type[BaseException], ...]] = (
    *WEBSOCKET_TRANSPORT_TERMINAL_EXCEPTIONS,
    asyncio.CancelledError,
)


def should_close_websocket_application_state(websocket: WebSocket) -> bool:
    return websocket.application_state == WebSocketState.CONNECTED


def is_websocket_close_state_error(exception: RuntimeError) -> bool:
    message = str(exception)
    return (
        (
            "Expected ASGI message 'websocket.send' or 'websocket.close'" in message
            and "websocket.close" in message
        )
        or (
            "Unexpected ASGI message 'websocket.close'" in message
            and "after sending 'websocket.close'" in message
        )
        or 'Cannot call "send" once a close message has been sent.' in message
    )
