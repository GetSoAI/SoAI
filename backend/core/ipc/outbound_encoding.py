"""SoAI - Bounded outbound IPC message encoding [backend/core/ipc/outbound_encoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial

from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    run_bounded_blocking_call,
)
from core.ipc.message_encoding import encode_ipc_message_bytes
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC
from core.types.json import JSONDict

__all__ = ("encode_outbound_ipc_message",)


async def encode_outbound_ipc_message(
    blocking_pool: BoundedBlockingPool,
    message: JSONDict,
    *,
    max_bytes: int,
    details: JSONDict,
    operation: str,
) -> bytes:
    invocation = partial(
        encode_ipc_message_bytes,
        message,
        max_bytes=max_bytes,
        details=details,
        operation=operation,
    )
    return await run_bounded_blocking_call(
        blocking_pool,
        invocation,
        total_timeout_sec=LONG_REQUEST_TIMEOUT_SEC,
    )
