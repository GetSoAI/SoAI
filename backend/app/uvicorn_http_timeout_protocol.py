"""SoAI - Uvicorn HTTP protocol with incomplete-header timeout [backend/app/uvicorn_http_timeout_protocol.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import override

from uvicorn.config import Config
from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
from uvicorn.server import ServerState

from core.errors.exceptions import StateError
from core.types.json import JSONValue

__all__ = (
    "SOAI_HTTP_REQUEST_HEADER_TIMEOUT_SECONDS",
    "SoAIHttpToolsProtocol",
)

SOAI_HTTP_REQUEST_HEADER_TIMEOUT_SECONDS = 5.0
_REQUEST_TIMEOUT_BODY = b"Request Timeout"


def _build_request_timeout_response() -> bytes:
    return b"".join(
        (
            b"HTTP/1.1 408 Request Timeout\r\n",
            b"content-type: text/plain; charset=utf-8\r\n",
            b"content-length: ",
            str(len(_REQUEST_TIMEOUT_BODY)).encode("ascii"),
            b"\r\nconnection: close\r\n\r\n",
            _REQUEST_TIMEOUT_BODY,
        )
    )


class SoAIHttpToolsProtocol(HttpToolsProtocol):
    def __init__(
        self,
        config: Config,
        server_state: ServerState,
        app_state: dict[str, JSONValue],
        _loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        super().__init__(config, server_state, app_state, _loop)
        self._soai_header_timeout_handle: asyncio.TimerHandle | None = None

    @override
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        if not isinstance(transport, asyncio.Transport):
            raise StateError("SoAI HTTP protocol requires an asyncio transport.")
        super().connection_made(transport)
        self._arm_soai_header_timeout()

    @override
    def connection_lost(self, exc: Exception | None) -> None:
        self._cancel_soai_header_timeout()
        super().connection_lost(exc)

    @override
    def data_received(self, data: bytes) -> None:
        if self.cycle is None or self.cycle.response_complete:
            self._arm_soai_header_timeout()
        super().data_received(data)

    @override
    def on_headers_complete(self) -> None:
        self._cancel_soai_header_timeout()
        super().on_headers_complete()

    def _arm_soai_header_timeout(self) -> None:
        if self._soai_header_timeout_handle is not None:
            return
        self._soai_header_timeout_handle = self.loop.call_later(
            SOAI_HTTP_REQUEST_HEADER_TIMEOUT_SECONDS,
            self._handle_soai_header_timeout,
        )

    def _cancel_soai_header_timeout(self) -> None:
        timeout_handle = self._soai_header_timeout_handle
        if timeout_handle is None:
            return
        timeout_handle.cancel()
        self._soai_header_timeout_handle = None

    def _handle_soai_header_timeout(self) -> None:
        self._soai_header_timeout_handle = None
        if self.transport.is_closing():
            return
        self.transport.write(_build_request_timeout_response())
        self.transport.close()
