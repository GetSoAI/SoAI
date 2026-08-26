"""SoAI - Multiplexed IPC request message writing [backend/core/ipc/multiplexed_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.ipc.multiplexed_support import MultiplexedConnection
from core.types.json import JSONDict

__all__ = (
    "build_ipc_request_message",
    "write_ipc_request_message_bytes",
)


def build_ipc_request_message(
    *,
    method: str,
    request_id: str,
    payload: JSONDict,
) -> JSONDict:
    return {
        "type": "request",
        "request_id": request_id,
        "method": method,
        "payload": dict(payload),
    }


async def write_ipc_request_message_bytes(
    *,
    connection: MultiplexedConnection,
    data: bytes,
    timeout_sec: float,
) -> None:
    async with connection.write_lock:
        connection.writer.write(data)
        timeout_value = max(0.1, float(timeout_sec))
        await asyncio.wait_for(connection.writer.drain(), timeout=timeout_value)
