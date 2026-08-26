"""SoAI - Multiplexed IPC connection read loop [backend/core/ipc/multiplexed_connection_reader.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.ipc.multiplexed_message_dispatch import dispatch_ipc_message
from core.ipc.multiplexed_support import MultiplexedConnection
from core.ipc.ndjson import IpcStreamClosedError, NdjsonCodec
from core.types.json import JSONDict

__all__ = ("read_multiplexed_connection",)


async def read_multiplexed_connection(
    *,
    codec: NdjsonCodec,
    host_request_handler: Callable[[int, str, JSONDict], Awaitable[JSONDict]] | None,
    connection: MultiplexedConnection,
) -> None:
    try:
        while True:
            message = await codec.read_message(
                connection.reader,
                timeout_sec=None,
            )
            await dispatch_ipc_message(
                codec=codec,
                host_request_handler=host_request_handler,
                connection=connection,
                message=message,
            )
    except IpcStreamClosedError:
        return
