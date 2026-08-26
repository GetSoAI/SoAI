"""SoAI - Orchestrator stream iteration with timeout enforcement [backend/orchestrator/execution/stream_iteration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, AsyncIterator, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.async_iterators import close_async_iterator_if_supported
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.tasks.task import Task
from orchestrator.execution.internal_protocols import ActiveInferenceRegistryProtocol
from orchestrator.execution.streaming import (
    build_stream_timeout_error,
    coerce_stream_chunk,
)

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk

__all__ = (
    "StreamIterationRequest",
    "build_stream_iterator",
    "iterate_stream_chunks",
)


@dataclass(frozen=True, slots=True)
class StreamIterationRequest:
    queue: OrchestratorQueueProtocol
    active_inferences: ActiveInferenceRegistryProtocol
    task: Task
    result: AsyncIterable[StreamChunk]
    tracking_id: str
    first_chunk_timeout: float
    streaming_idle_timeout: float
    detect_progress: Callable[[bytes], bool]


def build_stream_iterator(request: StreamIterationRequest) -> AsyncIterator[bytes]:
    return iterate_stream_chunks(
        queue=request.queue,
        active_inferences=request.active_inferences,
        task=request.task,
        result=request.result,
        tracking_id=request.tracking_id,
        first_chunk_timeout=request.first_chunk_timeout,
        streaming_idle_timeout=request.streaming_idle_timeout,
        detect_progress=request.detect_progress,
    )


async def iterate_stream_chunks(
    *,
    queue: OrchestratorQueueProtocol,
    active_inferences: ActiveInferenceRegistryProtocol,
    task: Task,
    result: AsyncIterable[StreamChunk],
    tracking_id: str,
    first_chunk_timeout: float,
    streaming_idle_timeout: float,
    detect_progress: Callable[[bytes], bool],
) -> AsyncIterator[bytes]:
    iterator = aiter(result)
    event_loop = asyncio.get_running_loop()
    timeout_seconds = first_chunk_timeout
    progress_deadline = event_loop.time() + timeout_seconds

    try:
        while True:
            remaining_timeout = max(0.0, progress_deadline - event_loop.time())
            timeout_scope = asyncio.timeout(remaining_timeout)
            try:
                async with timeout_scope:
                    raw_chunk = await anext(iterator)
            except StopAsyncIteration:
                break
            except TimeoutError as timeout_exc:
                raise build_stream_timeout_error(timeout_scope, timeout_seconds) from timeout_exc
            if await queue.is_task_cancelled(task):
                raise asyncio.CancelledError()
            chunk_bytes = coerce_stream_chunk(raw_chunk)
            if detect_progress(chunk_bytes):
                timeout_seconds = streaming_idle_timeout
                progress_deadline = event_loop.time() + timeout_seconds
                await active_inferences.update_progress(tracking_id)
            yield chunk_bytes
    finally:
        await close_async_iterator_if_supported(iterator)
