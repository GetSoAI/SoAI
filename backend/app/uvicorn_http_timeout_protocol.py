"""SoAI - Uvicorn HTTP protocol with incomplete-header timeout [backend/app/uvicorn_http_timeout_protocol.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from functools import cache
from typing import override

from uvicorn.config import Config
from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
from uvicorn.server import ServerState

from core.errors.exceptions import StateError
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.types.json import JSONValue

__all__ = (
    "SOAI_HTTP_REQUEST_HEADER_TIMEOUT_SECONDS",
    "SoAIHttpToolsProtocol",
)

SOAI_HTTP_REQUEST_HEADER_TIMEOUT_SECONDS = 5.0
_REQUEST_TIMEOUT_BODY = b"Request Timeout"
LOGGER_NAME = "SoAI.app.uvicorn_http_timeout_protocol"
HEADER_TIMEOUT_DIAGNOSTIC_INTERVAL_SECONDS = 60.0
HEADER_TIMEOUT_BEFORE_FIRST_REQUEST = "before_first_request"
HEADER_TIMEOUT_INCOMPLETE_HEADERS = "incomplete_headers"


@cache
def _header_timeout_diagnostics() -> dict[str, RateLimitedLogger]:
    return {
        phase: RateLimitedLogger(interval_seconds=HEADER_TIMEOUT_DIAGNOSTIC_INTERVAL_SECONDS)
        for phase in (HEADER_TIMEOUT_BEFORE_FIRST_REQUEST, HEADER_TIMEOUT_INCOMPLETE_HEADERS)
    }


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
        self._soai_connected_at = self.loop.time()
        self._soai_header_bytes = 0
        self._soai_started_requests = 0

    @override
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        if not isinstance(transport, asyncio.Transport):
            raise StateError("SoAI HTTP protocol requires an asyncio transport.")
        super().connection_made(transport)
        self._soai_connected_at = self.loop.time()
        self._arm_soai_header_timeout()

    @override
    def connection_lost(self, exc: Exception | None) -> None:
        self._cancel_soai_header_timeout()
        super().connection_lost(exc)

    @override
    def shutdown(self) -> None:
        self._cancel_soai_header_timeout()
        self._unset_keepalive_if_required()
        if self.transport.is_closing():
            return
        super().shutdown()

    @override
    def data_received(self, data: bytes) -> None:
        if self.cycle is None or self.cycle.response_complete:
            self._arm_soai_header_timeout()
        if self._soai_header_timeout_handle is not None:
            self._soai_header_bytes += len(data)
        super().data_received(data)

    @override
    def on_headers_complete(self) -> None:
        self._cancel_soai_header_timeout()
        self._soai_started_requests += 1
        super().on_headers_complete()

    def _arm_soai_header_timeout(self) -> None:
        if self._soai_header_timeout_handle is not None:
            return
        self._soai_header_bytes = 0
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
        self._record_soai_header_timeout()
        if self._soai_header_bytes:
            self.transport.write(_build_request_timeout_response())
        self.transport.close()

    def _record_soai_header_timeout(self) -> None:
        phase = (
            HEADER_TIMEOUT_INCOMPLETE_HEADERS
            if self._soai_header_bytes
            else HEADER_TIMEOUT_BEFORE_FIRST_REQUEST
        )
        emit, suppressed = _header_timeout_diagnostics()[phase].should_emit()
        if not emit:
            return
        get_logger(LOGGER_NAME).info(
            (
                "HTTP request header timeout: phase=%s header_bytes=%s started_requests=%s "
                "connection_age_ms=%s peer=%s suppressed=%s"
            ),
            phase,
            self._soai_header_bytes,
            self._soai_started_requests,
            int((self.loop.time() - self._soai_connected_at) * 1000),
            self.transport.get_extra_info("peername"),
            suppressed,
        )
