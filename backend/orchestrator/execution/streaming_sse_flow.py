"""SoAI - OpenAI SSE streaming flow handling [backend/orchestrator/execution/streaming_sse_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.async_iterators import close_async_iterator_if_supported
from core.errors.exceptions import ModelOutputContractError, StateError
from core.logging.protocols import TraceLogger
from core.openai.openai_error_objects import parse_openai_sse_error_frame
from core.openai.openai_sse_error_escalation import raise_openai_streaming_error
from core.openai.responses_stream_transcript import ResponsesStreamTranscript
from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
from core.openai.sse_progress import OpenAISSEProgressDetector
from core.openai.sse_validation import validate_openai_sse_frame
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.openai.streaming_usage import StreamingUsageCollector
from core.openai.transcription_stream_transcript import OpenAITranscriptionStreamTranscript
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.tasks.task import Task
from core.tasks.type_catalog import (
    TASK_TYPE_AUDIO_TRANSCRIPTION,
    TASK_TYPE_OPENAI_RESPONSE,
)
from core.types.json import JSONDict
from orchestrator.execution.image_sse_transcript import ImageSSETranscript
from orchestrator.execution.internal_protocols import ActiveInferenceRegistryProtocol
from orchestrator.execution.stream_delivery import deliver_stream_chunk
from orchestrator.execution.stream_iteration import StreamIterationRequest, build_stream_iterator
from orchestrator.execution.streaming_result_resolution import build_stream_transcript
from orchestrator.execution.token_stream_progress import TokenStreamProgressSampler

if TYPE_CHECKING:
    from core.metrics.protocols import TokenStreamMetricsProtocol
    from core.openai.protocols_usage import CompletionTokenTranscriptProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.streaming.stream_chunk import StreamChunk

__all__ = (
    "StreamingSSEFlowResult",
    "build_streaming_final_result",
    "process_streaming_sse_flow",
)


@dataclass(frozen=True, slots=True)
class StreamingSSEFlowResult:
    transcript: OpenAIStreamTranscript | None
    responses_transcript: ResponsesStreamTranscript | None
    transcription_transcript: OpenAITranscriptionStreamTranscript | None
    image_transcript: ImageSSETranscript | None
    deferred_terminal_chunks: tuple[bytes, ...] = ()


async def process_streaming_sse_flow(
    *,
    queue: OrchestratorQueueProtocol,
    active_inferences: ActiveInferenceRegistryProtocol,
    task: Task,
    result: AsyncIterable[StreamChunk],
    tracking_id: str,
    streaming_chunk_delivery_timeout: float,
    first_chunk_timeout: float,
    streaming_idle_timeout: float,
    operation: str,
    logger: TraceLogger,
    include_transcript: bool,
    image_transcript: ImageSSETranscript | None,
    usage_collector: StreamingUsageCollector | None,
    metrics: TokenStreamMetricsProtocol,
    prompt_token_counter: PromptTokenCounter,
    plugin_name: str,
    model_name: str | None = None,
) -> StreamingSSEFlowResult:
    responses_transcript = (
        ResponsesStreamTranscript(
            response_id=task.task_id,
            model=_resolve_requested_model(queue=queue, task=task),
            created_at=max(1, task.created_at_ms // 1000),
        )
        if include_transcript and task.task_type == TASK_TYPE_OPENAI_RESPONSE
        else None
    )
    transcription_transcript = (
        OpenAITranscriptionStreamTranscript()
        if task.task_type == TASK_TYPE_AUDIO_TRANSCRIPTION
        else None
    )
    transcript = (
        build_stream_transcript(queue=queue, task=task)
        if include_transcript and responses_transcript is None and transcription_transcript is None
        else None
    )
    token_transcript: CompletionTokenTranscriptProtocol | None = (
        responses_transcript or transcription_transcript or transcript
    )
    progress_sampler = TokenStreamProgressSampler(
        metrics=metrics,
        prompt_token_counter=prompt_token_counter,
        stream_id=task.task_id,
        plugin_name=plugin_name,
        model_name=model_name or _resolve_requested_model(queue=queue, task=task),
    )
    iteration_request = StreamIterationRequest(
        queue=queue,
        active_inferences=active_inferences,
        task=task,
        result=result,
        tracking_id=tracking_id,
        first_chunk_timeout=first_chunk_timeout,
        streaming_idle_timeout=streaming_idle_timeout,
        detect_progress=OpenAISSEProgressDetector().consume,
    )
    stream_iterator = build_stream_iterator(iteration_request)
    frame_accumulator = OpenAISSEFrameAccumulator()
    deferred_terminal_chunks: list[bytes] = []
    terminal_observed = False
    if token_transcript is not None:
        progress_sampler.begin()
    try:
        async for chunk_bytes in stream_iterator:
            for frame_text in frame_accumulator.feed(chunk_bytes):
                if not validate_openai_sse_frame(
                    frame_text,
                    allow_responses_events=task.task_type == TASK_TYPE_OPENAI_RESPONSE,
                    allow_image_events=image_transcript is not None,
                    allow_transcription_events=transcription_transcript is not None,
                ):
                    raise ModelOutputContractError(
                        "Provider returned a malformed OpenAI SSE frame.",
                        operation=operation,
                        details={"failure_type": "malformed_frame"},
                    )
                parsed_error = parse_openai_sse_error_frame(frame_text)
                if parsed_error is not None:
                    raise_openai_streaming_error(parsed_error, operation=operation)
                frame_bytes = frame_text.encode("utf-8")
                if usage_collector is not None:
                    usage_collector.consume_frame(frame_text)
                if transcript is not None:
                    transcript.feed(frame_bytes)
                if responses_transcript is not None:
                    terminal_before_frame = responses_transcript.terminal_observed
                    responses_transcript.consume_frame(frame_text)
                    if not terminal_before_frame and responses_transcript.terminal_observed:
                        deferred_terminal_chunks.append(frame_bytes)
                        terminal_observed = True
                    if terminal_observed:
                        continue
                if transcription_transcript is not None:
                    terminal_before_frame = transcription_transcript.terminal_observed
                    transcription_transcript.feed(frame_bytes)
                    if not terminal_before_frame and transcription_transcript.terminal_observed:
                        deferred_terminal_chunks.append(frame_bytes)
                        terminal_observed = True
                    if terminal_observed:
                        continue
                if image_transcript is not None:
                    image_transcript.feed(frame_bytes)
                if token_transcript is not None:
                    progress_sampler.sample(token_transcript)
                await deliver_stream_chunk(
                    task=task,
                    chunk_bytes=frame_bytes,
                    streaming_chunk_delivery_timeout=streaming_chunk_delivery_timeout,
                    operation=operation,
                    logger=logger,
                )
            if terminal_observed:
                break
        if token_transcript is not None:
            progress_sampler.sample(token_transcript, force=True)
    finally:
        try:
            await close_async_iterator_if_supported(stream_iterator)
        finally:
            progress_sampler.finish()
    frame_accumulator.finalize()
    if transcript is not None:
        transcript.finalize()
    if responses_transcript is not None:
        responses_transcript.finalize()
    if transcription_transcript is not None:
        transcription_transcript.finalize()
    if image_transcript is not None:
        image_transcript.finalize()
    return StreamingSSEFlowResult(
        transcript=transcript,
        responses_transcript=responses_transcript,
        transcription_transcript=transcription_transcript,
        image_transcript=image_transcript,
        deferred_terminal_chunks=tuple(deferred_terminal_chunks),
    )


def build_streaming_final_result(
    flow_result: StreamingSSEFlowResult,
    *,
    usage: JSONDict | None = None,
) -> JSONDict:
    image_transcript = flow_result.image_transcript
    if image_transcript is not None:
        image_payload = image_transcript.build_result_payload()
        if image_payload is None:
            raise StateError("Image streaming completed without a final payload.")
        return image_payload
    responses_transcript = flow_result.responses_transcript
    if responses_transcript is not None:
        return responses_transcript.build_result_payload()
    transcription_transcript = flow_result.transcription_transcript
    if transcription_transcript is not None:
        return transcription_transcript.build_result_payload()
    transcript = flow_result.transcript
    if transcript is None:
        return {}
    return transcript.build_result_payload(usage=usage)


def _resolve_requested_model(*, queue: OrchestratorQueueProtocol, task: Task) -> str:
    context = queue.require_orchestration_context(task)
    event = context.event
    payload = event.payload if event is not None else None
    model = payload.get("model") if isinstance(payload, dict) else None
    return model if isinstance(model, str) else "unknown"
