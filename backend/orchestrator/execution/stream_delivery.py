"""SoAI - Streaming chunk delivery to task reply queues [backend/orchestrator/execution/stream_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_models_streaming import StreamChunkEvent
from core.logging.protocols import TraceLogger
from core.tasks.task import Task
from orchestrator.execution.streaming import ChunkDeliveryTimeoutError

__all__ = ("deliver_stream_chunk", "try_deliver_stream_chunks")

OPERATION_ORCHESTRATOR_EXECUTION_STREAM_DELIVERY_DELIVER_STREAM_CHUNK = (
    "orchestrator.execution.stream_delivery.deliver_stream_chunk"
)


async def deliver_stream_chunk(
    *,
    task: Task,
    chunk_bytes: bytes,
    streaming_chunk_delivery_timeout: float,
    operation: str,
    logger: TraceLogger,
) -> None:
    reply_queue = task.reply_queue
    if reply_queue is None:
        return
    try:
        await asyncio.wait_for(
            reply_queue.put(StreamChunkEvent(chunk=chunk_bytes)),
            timeout=streaming_chunk_delivery_timeout,
        )
    except TimeoutError as exception:
        raise ChunkDeliveryTimeoutError(streaming_chunk_delivery_timeout) from exception
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to deliver streaming chunk for task [{task.task_id}]",
            operation=OPERATION_ORCHESTRATOR_EXECUTION_STREAM_DELIVERY_DELIVER_STREAM_CHUNK,
            details={"task_id": task.task_id, "operation": operation},
        )
        raise


async def try_deliver_stream_chunks(
    *,
    task: Task,
    chunks: tuple[bytes, ...],
    streaming_chunk_delivery_timeout: float,
    operation: str,
    logger: TraceLogger,
) -> bool:
    try:
        for chunk_bytes in chunks:
            await deliver_stream_chunk(
                task=task,
                chunk_bytes=chunk_bytes,
                streaming_chunk_delivery_timeout=streaming_chunk_delivery_timeout,
                operation=operation,
                logger=logger,
            )
    except HANDLED_RUNTIME_EXCEPTIONS:
        return False
    return True
