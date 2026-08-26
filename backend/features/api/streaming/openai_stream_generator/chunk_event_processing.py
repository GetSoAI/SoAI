"""SoAI - StreamChunkEvent processing for OpenAI SSE [backend/features/api/streaming/openai_stream_generator/chunk_event_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Iterator

from core.errors.exceptions import ModelOutputContractError
from core.events.types_models_streaming import StreamChunkEvent
from core.logging.protocols import LoggerProtocol
from core.openai.quota_enforcement_constants import (
    STREAMING_MAX_TOKENS_CUTOFF_REASON,
    STREAMING_QUOTA_CUTOFF_REASON,
)
from core.openai.sse_frames import sse_done_chunk
from core.openai.sse_validation import validate_openai_sse_frame
from core.openai.stream_frame_processing import process_openai_stream_frame
from core.openai.streaming_text_deltas import (
    extract_openai_streaming_all_output_deltas,
    extract_openai_streaming_output_deltas,
)
from core.openai.streaming_tool_calls import rewrite_missing_tool_call_ids_in_sse_frame
from features.api.streaming.openai_stream_generator.provider_error_frames import (
    raise_provider_sse_error_if_present,
)
from features.api.streaming.openai_stream_generator.runtime_state import (
    OpenAIStreamRuntimeState,
)
from features.api.streaming.openai_stream_generator.stream_abort import (
    OpenAIStreamAbortRequested,
)

__all__ = ("iter_stream_bytes_from_chunk_event",)


def _rewrite_sse_tool_call_ids(state: OpenAIStreamRuntimeState, chunk_text: str) -> str:
    return rewrite_missing_tool_call_ids_in_sse_frame(
        chunk_text,
        tool_call_ids_by_index=state.tool_call_ids_by_index,
        tool_call_ids_by_ordinal=state.tool_call_ids_by_ordinal,
    )


def iter_stream_bytes_from_chunk_event(
    chunk_event: StreamChunkEvent,
    state: OpenAIStreamRuntimeState,
    *,
    trace_id: str,
    logger: LoggerProtocol,
    schedule_task_cancel: Callable[[str], None],
    allow_image_events: bool = False,
    emit_done_marker: bool,
) -> Iterator[bytes]:
    try:
        frames = state.chunk_accumulator.feed(chunk_event.chunk)
    except ModelOutputContractError as exception:
        message = "Provider returned an invalid OpenAI SSE byte stream."
        state.is_stream_successful = False
        state.abort_stream = True
        schedule_task_cancel(message)
        raise OpenAIStreamAbortRequested(message, "invalid_stream_error") from exception
    for validated_sse_event in frames:
        if not validate_openai_sse_frame(
            validated_sse_event,
            allow_image_events=allow_image_events,
        ):
            message = "Provider returned a malformed OpenAI SSE frame."
            logger.warning("[%s] %s", trace_id, message)
            state.is_stream_successful = False
            state.abort_stream = True
            schedule_task_cancel(message)
            raise OpenAIStreamAbortRequested(message, "invalid_stream_error")
        try:
            raise_provider_sse_error_if_present(validated_sse_event)
        except OpenAIStreamAbortRequested as exception:
            state.is_stream_successful = False
            state.abort_stream = True
            schedule_task_cancel(exception.message)
            raise
        frame = process_openai_stream_frame(validated_sse_event)
        if not state.stream_id and frame.stream_id is not None:
            state.stream_id = frame.stream_id
        if not state.stream_object and frame.stream_object is not None:
            state.stream_object = frame.stream_object
        filtered_chunk_text = frame.filtered_text
        if filtered_chunk_text.strip():
            if state.collect_tool_calls:
                filtered_chunk_text = _rewrite_sse_tool_call_ids(state, filtered_chunk_text)
            max_token_budget = state.max_completion_token_budget
            if max_token_budget is not None and max_token_budget.add_texts(
                extract_openai_streaming_all_output_deltas(
                    filtered_chunk_text,
                    include_tool_calls=state.collect_tool_calls,
                ),
            ):
                state.abort_stream = True
                state.done_marker_observed = True
                transcript = state.stream_transcript
                if transcript is not None:
                    transcript.set_finish_reason("length")
                schedule_task_cancel(STREAMING_MAX_TOKENS_CUTOFF_REASON)
                if emit_done_marker and not state.is_done_sent:
                    yield sse_done_chunk()
                    state.is_done_sent = True
                break
            quota_budget = state.quota_completion_token_budget
            if quota_budget is not None and quota_budget.add_texts(
                extract_openai_streaming_output_deltas(
                    filtered_chunk_text,
                    include_tool_calls=state.collect_tool_calls,
                ),
            ):
                state.is_stream_successful = False
                state.abort_stream = True
                schedule_task_cancel(STREAMING_QUOTA_CUTOFF_REASON)
                raise OpenAIStreamAbortRequested(
                    STREAMING_QUOTA_CUTOFF_REASON,
                    "insufficient_quota",
                )
            if state.stream_transcript is not None:
                state.stream_transcript.feed(filtered_chunk_text)
            yield filtered_chunk_text.encode("utf-8")
        if frame.done_marker_observed:
            state.done_marker_observed = True
