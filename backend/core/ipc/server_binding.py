"""SoAI - IPC loopback server binding primitive [backend/core/ipc/server_binding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.errors.exceptions import ValidationError

__all__ = ("BoundLoopbackServer", "bind_loopback_ipc_server")


@dataclass(frozen=True, slots=True)
class BoundLoopbackServer:
    server: asyncio.Server
    host: str
    port: int


async def bind_loopback_ipc_server(
    handler: Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]],
    *,
    stream_limit_bytes: int,
) -> BoundLoopbackServer:
    server = await asyncio.start_server(
        handler,
        host="127.0.0.1",
        port=0,
        limit=stream_limit_bytes,
    )
    sockets: list[socket.socket] = list(server.sockets or [])
    if not sockets:
        raise ValidationError("IPC server did not bind to a socket.")
    sockname = sockets[0].getsockname()
    return BoundLoopbackServer(server=server, host=str(sockname[0]), port=int(sockname[1]))
