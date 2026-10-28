"""SoAI - WebSocket transport lifecycle policy [backend/features/api/routes/system/events/websocket_transport_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from fastapi import WebSocket, WebSocketDisconnect
from starlette.requests import ClientDisconnect
from starlette.websockets import WebSocketState

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "WEBSOCKET_CLIENT_DISCONNECT_EXCEPTIONS",
    "WEBSOCKET_TERMINAL_LIFECYCLE_EXCEPTIONS",
    "WEBSOCKET_TRANSPORT_TERMINAL_EXCEPTIONS",
    "WebsocketTerminalErrorDelivery",
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


@dataclass(slots=True)
class WebsocketTerminalErrorDelivery:
    payload: JSONDict | None = None
    requested: asyncio.Event = field(default_factory=asyncio.Event)
    delivered: asyncio.Event = field(default_factory=asyncio.Event)


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
