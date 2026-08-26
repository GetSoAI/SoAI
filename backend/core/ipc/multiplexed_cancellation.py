"""SoAI - Multiplexed IPC cancellation requests [backend/core/ipc/multiplexed_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from enum import StrEnum

from core.ipc.multiplexed_support import MultiplexedConnection
from core.ipc.ndjson import NdjsonCodec
from core.types.json import JSONDict

__all__ = ("WorkerCancellationOutcome", "cancel_worker_call")


class WorkerCancellationOutcome(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    NOT_ACKNOWLEDGED = "not_acknowledged"
    REJECTED = "rejected"


async def cancel_worker_call(
    *,
    codec: NdjsonCodec,
    connection: MultiplexedConnection,
    target_request_id: str,
    timeout_sec: float,
) -> WorkerCancellationOutcome:
    cancel_request_id = f"{target_request_id}.cancel"
    loop = asyncio.get_running_loop()
    future: asyncio.Future[JSONDict] = loop.create_future()
    connection.pending[cancel_request_id] = future
    message: JSONDict = {
        "type": "request",
        "request_id": cancel_request_id,
        "method": "worker.cancel_call",
        "payload": {"request_id": target_request_id},
    }
    try:
        async with connection.write_lock:
            await codec.write_message(connection.writer, message, timeout_sec=5.0)
        try:
            response = await asyncio.wait_for(future, timeout=max(0.1, timeout_sec))
        except TimeoutError:
            return WorkerCancellationOutcome.NOT_ACKNOWLEDGED
        if response.get("ok") is True:
            return WorkerCancellationOutcome.ACKNOWLEDGED
        return WorkerCancellationOutcome.REJECTED
    finally:
        connection.pending.pop(cancel_request_id, None)
