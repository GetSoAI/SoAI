"""SoAI - Orchestrator streaming response buffering into unary results [backend/orchestrator/execution/stream_buffering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterable
from typing import TYPE_CHECKING

from core.concurrency.async_iterators import close_async_iterator_if_supported
from core.config.numeric import coerce_positive_float
from core.events.types_tasks import TaskProgressEvent
from core.openai.sse_progress import OpenAISSEProgressDetector
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.tasks.streaming_prefill_timeout import resolve_streaming_first_chunk_timeout
from core.tasks.task import Task
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC, LONG_REQUEST_TIMEOUT_SEC
from orchestrator.execution.internal_protocols import ActiveInferenceRegistryProtocol
from orchestrator.execution.stream_iteration import StreamIterationRequest, build_stream_iterator
from orchestrator.execution.streaming import STREAMING_IDLE_TIMEOUT_MINIMUM
from orchestrator.execution.token_stream_progress import TokenStreamProgressSampler

if TYPE_CHECKING:
    from core.metrics.protocols import TokenStreamMetricsProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.streaming.stream_chunk import StreamChunk
    from core.types.json import JSONDict

__all__ = ("buffer_stream_to_result_payload",)


async def buffer_stream_to_result_payload(
    *,
    queue: OrchestratorQueueProtocol,
    active_inferences: ActiveInferenceRegistryProtocol,
    task: Task,
    result: AsyncIterable[StreamChunk],
    health_check_config: JSONDict,
    metrics: TokenStreamMetricsProtocol,
    prompt_token_counter: PromptTokenCounter,
    plugin_name: str,
    model_name: str | None = None,
) -> JSONDict:
    context = queue.require_orchestration_context(task)
    first_chunk_timeout = resolve_streaming_first_chunk_timeout(
        task=task,
        health_check_config=health_check_config,
    )
    streaming_idle_timeout = coerce_positive_float(
        health_check_config.get(
            "STREAMING_IDLE_TIMEOUT_SEC",
            LONG_REQUEST_TIMEOUT_SEC,
        ),
        default=LONG_REQUEST_TIMEOUT_SEC,
        minimum=STREAMING_IDLE_TIMEOUT_MINIMUM,
    )
    model_hint = None
    event = context.event
    if event is not None:
        requested_model = event.payload.get("model")
        model_hint = requested_model if isinstance(requested_model, str) else None
    transcript = OpenAIStreamTranscript(model_hint=model_hint)
    progress_sampler = TokenStreamProgressSampler(
        metrics=metrics,
        prompt_token_counter=prompt_token_counter,
        stream_id=task.task_id,
        plugin_name=plugin_name,
        model_name=model_name or model_hint,
    )
    last_activity_event_at = 0.0
    reply_queue = task.reply_queue
    stream_iterator = build_stream_iterator(
        StreamIterationRequest(
            queue=queue,
            active_inferences=active_inferences,
            task=task,
            result=result,
            tracking_id=context.tracking_id,
            first_chunk_timeout=first_chunk_timeout,
            streaming_idle_timeout=streaming_idle_timeout,
            detect_progress=OpenAISSEProgressDetector().consume,
        ),
    )
    progress_sampler.begin()
    try:
        async for chunk_bytes in stream_iterator:
            transcript.feed(chunk_bytes)
            progress_sampler.sample(transcript)
            if reply_queue is not None:
                now = time.monotonic()
                if now - last_activity_event_at >= INTERACTIVE_TIMEOUT_SEC:
                    last_activity_event_at = now
                    try:
                        reply_queue.put_nowait(
                            TaskProgressEvent(
                                percent=0,
                                message="",
                                details="",
                                task_id=task.task_id,
                                user_id=task.user_id,
                            ),
                        )
                    except asyncio.QueueFull:
                        continue
        progress_sampler.sample(transcript, force=True)
    finally:
        try:
            await close_async_iterator_if_supported(stream_iterator)
        finally:
            progress_sampler.finish()
    transcript.finalize()
    return transcript.build_result_payload()
