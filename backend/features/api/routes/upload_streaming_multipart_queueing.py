"""SoAI - Streaming multipart parser queue backpressure handling [backend/features/api/routes/upload_streaming_multipart_queueing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import queue
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_after
from core.timing.constants import CONTROL_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from features.api.routes.upload_streaming_multipart_worker_state import (
        StreamingMultipartWorkerState,
    )

__all__ = ("enqueue_parser_chunk",)

_PARSER_QUEUE_PUT_RETRY_SEC: float = 0.25


async def enqueue_parser_chunk(
    state: StreamingMultipartWorkerState,
    *,
    item: bytes | None,
    token: CancellationTokenProtocol,
) -> bool:
    deadline = deadline_after(CONTROL_TIMEOUT_SEC)
    while True:
        state.raise_if_failed()
        token.raise_if_cancelled()
        try:
            state.chunk_queue.put_nowait(item)
            return True
        except queue.Full:
            remaining = deadline.remaining_seconds()
            if remaining <= 0.0:
                return False
            wait_timeout = min(_PARSER_QUEUE_PUT_RETRY_SEC, remaining)
            await asyncio.sleep(wait_timeout)
