"""SoAI - Shared loopback IPC server base [backend/core/ipc/loopback_server_base.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import secrets

from core.errors.exceptions import StateError, ValidationError
from core.ipc.ndjson import NdjsonCodec
from core.ipc.server_binding import bind_loopback_ipc_server

__all__ = ("LoopbackIpcServerBase",)


class LoopbackIpcServerBase:
    def __init__(self, *, codec: NdjsonCodec) -> None:
        self._codec = codec
        self._server: asyncio.base_events.Server | None = None
        self._token = secrets.token_hex(32)
        self._bound_host: str | None = None
        self._bound_port: int | None = None

    @property
    def token(self) -> str:
        return self._token

    @property
    def host(self) -> str:
        if not self._bound_host:
            raise ValidationError("IPC server is not started.")
        return self._bound_host

    @property
    def port(self) -> int:
        if self._bound_port is None:
            raise ValidationError("IPC server is not started.")
        return int(self._bound_port)

    @property
    def max_message_bytes(self) -> int:
        return self._codec.max_line_bytes

    async def start(self) -> None:
        if self._server is not None:
            return
        bound_server = await bind_loopback_ipc_server(
            self._handle_connection,
            stream_limit_bytes=self._codec.stream_limit_bytes,
        )
        self._server = bound_server.server
        self._bound_host = bound_server.host
        self._bound_port = bound_server.port

    async def _shutdown_server(self) -> None:
        server = self._server
        self._server = None
        self._bound_host = None
        self._bound_port = None
        if server is None:
            return
        server.close()
        await server.wait_closed()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        raise StateError("IPC server connection handler is not configured.")
