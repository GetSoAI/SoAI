"""SoAI - Orchestrator stream iteration with timeout enforcement [backend/orchestrator/execution/stream_iteration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterable, AsyncIterator, Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.async_iterators import close_async_iterator_if_supported
from core.errors.exceptions import SoAITimeoutError
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.tasks.task import Task
from orchestrator.execution.execution_phase_timeouts import (
    ExecutionPhase,
    await_execution_phase,
    execution_phase_timeout_error,
)
from orchestrator.execution.internal_protocols import ActiveInferenceRegistryProtocol
from orchestrator.execution.streaming import (
    StreamingIdleTimeoutError,
    StreamingSourceTimeoutError,
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
    context = task.orchestration_context
    execution_budget = context.execution_budget if context is not None else None
    progress_deadline = (
        event_loop.time() + execution_budget.deadline.remaining_seconds()
        if execution_budget is not None
        else event_loop.time() + timeout_seconds
    )
    meaningful_output_seen = False

    def progress_timeout(wait_started: float, limit_seconds: float) -> SoAITimeoutError:
        if execution_budget is not None and not meaningful_output_seen:
            return execution_phase_timeout_error(
                execution_budget,
                ExecutionPhase.FIRST_TOKEN,
                wait_started_monotonic=wait_started,
                limit_seconds=limit_seconds,
            )
        return StreamingIdleTimeoutError(timeout_seconds)

    try:
        while True:
            remaining_timeout = max(0.0, progress_deadline - event_loop.time())
            wait_started = time.monotonic()
            try:
                raw_chunk = await await_execution_phase(
                    anext(iterator),
                    timeout_seconds=remaining_timeout,
                    timeout_error=partial(progress_timeout, wait_started, remaining_timeout),
                    task_registry=queue.task_registry,
                    task=task,
                )
            except StopAsyncIteration:
                break
            except TimeoutError as timeout_exc:
                raise StreamingSourceTimeoutError(timeout_seconds) from timeout_exc
            if await queue.is_task_cancelled(task):
                raise asyncio.CancelledError()
            chunk_bytes = coerce_stream_chunk(raw_chunk)
            if detect_progress(chunk_bytes):
                meaningful_output_seen = True
                timeout_seconds = streaming_idle_timeout
                progress_deadline = event_loop.time() + timeout_seconds
                await active_inferences.update_progress(tracking_id)
            yield chunk_bytes
    finally:
        await close_async_iterator_if_supported(iterator)
