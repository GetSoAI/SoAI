"""SoAI - Uvicorn WebSocket protocol with fragmented-message timeout [backend/app/uvicorn_websocket_timeout_protocol.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import override

from uvicorn.config import Config
from uvicorn.protocols.websockets.websockets_sansio_impl import WebSocketsSansIOProtocol
from uvicorn.server import ServerState
from websockets.exceptions import InvalidState
from websockets.frames import Frame

from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.types.json import JSONValue

__all__ = (
    "SOAI_WEBSOCKET_MESSAGE_ASSEMBLY_TIMEOUT_SECONDS",
    "SoAIWebSocketsSansIOProtocol",
)

SOAI_WEBSOCKET_MESSAGE_ASSEMBLY_TIMEOUT_SECONDS = LOCAL_IO_TIMEOUT_SEC
_MESSAGE_ASSEMBLY_TIMEOUT_CLOSE_CODE = 1008
_MESSAGE_ASSEMBLY_TIMEOUT_REASON = "Message assembly timeout"


class SoAIWebSocketsSansIOProtocol(WebSocketsSansIOProtocol):
    def __init__(
        self,
        config: Config,
        server_state: ServerState,
        app_state: dict[str, JSONValue],
        _loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        super().__init__(config, server_state, app_state, _loop)
        self._soai_message_timeout_handle: asyncio.TimerHandle | None = None

    @override
    def connection_lost(self, exc: Exception | None) -> None:
        self._cancel_soai_message_timeout()
        super().connection_lost(exc)

    @override
    def handle_text(self, event: Frame) -> None:
        super().handle_text(event)
        if event.fin:
            self._cancel_soai_message_timeout()
            return
        self._arm_soai_message_timeout()

    @override
    def handle_bytes(self, event: Frame) -> None:
        super().handle_bytes(event)
        if event.fin:
            self._cancel_soai_message_timeout()
            return
        self._arm_soai_message_timeout()

    @override
    def handle_cont(self, event: Frame) -> None:
        super().handle_cont(event)
        if event.fin:
            self._cancel_soai_message_timeout()

    @override
    def handle_close(self, event: Frame) -> None:
        self._cancel_soai_message_timeout()
        super().handle_close(event)

    @override
    def handle_parser_exception(self) -> None:
        self._cancel_soai_message_timeout()
        super().handle_parser_exception()

    def _arm_soai_message_timeout(self) -> None:
        if self._soai_message_timeout_handle is not None:
            return
        self._soai_message_timeout_handle = self.loop.call_later(
            SOAI_WEBSOCKET_MESSAGE_ASSEMBLY_TIMEOUT_SECONDS,
            self._handle_soai_message_timeout,
        )

    def _cancel_soai_message_timeout(self) -> None:
        timeout_handle = self._soai_message_timeout_handle
        if timeout_handle is None:
            return
        timeout_handle.cancel()
        self._soai_message_timeout_handle = None

    def _handle_soai_message_timeout(self) -> None:
        self._soai_message_timeout_handle = None
        if self.close_sent or self.transport.is_closing():
            return
        try:
            self.conn.send_close(
                _MESSAGE_ASSEMBLY_TIMEOUT_CLOSE_CODE,
                _MESSAGE_ASSEMBLY_TIMEOUT_REASON,
            )
        except InvalidState:
            self.close_sent = True
            self.transport.close()
            return
        self.transport.write(b"".join(self.conn.data_to_send()))
        self.close_sent = True
        self.transport.close()
