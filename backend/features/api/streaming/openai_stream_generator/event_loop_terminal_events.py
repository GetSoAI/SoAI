"""SoAI - OpenAI stream generator terminal event handlers [backend/features/api/streaming/openai_stream_generator/event_loop_terminal_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import TYPE_CHECKING

from core.errors.http_status_classification import (
    resolve_openai_error_type_for_http_status,
)
from core.errors.status_mapping import error_type_to_status_code
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent
from core.openai.openai_error_objects import (
    build_openai_error_payload,
    normalize_openai_error_code_subtype,
)
from core.openai.sse_events import format_openai_sse_bytes
from core.openai.sse_frames import sse_done_chunk
from core.streaming.protocols import StreamGeneratorStateProtocol
from core.tasks.enums import TaskStatus
from features.api.streaming.openai_stream_generator.end_event_processing import (
    finalize_openai_stream_frames,
    iter_public_usage_chunk,
)
from features.api.streaming.openai_stream_generator.stream_abort import (
    OpenAIStreamAbortRequested,
)
from features.api.streaming.stream_iteration import (
    StreamTermination,
    StreamTerminationReason,
)

if TYPE_CHECKING:
    from features.api.streaming.openai_stream_generator.runtime_state import (
        OpenAIStreamRuntimeState,
    )

__all__ = (
    "iter_error_event_chunks",
    "iter_task_complete_chunks",
    "iter_termination_chunks",
)


async def iter_termination_chunks(
    classified: StreamTermination,
    state: OpenAIStreamRuntimeState,
    *,
    emit_done_marker: bool,
    send_error: Callable[[str, str], AsyncGenerator[bytes]],
    stream_result_state: StreamGeneratorStateProtocol | None,
    include_usage: bool,
    model: str | None,
) -> AsyncGenerator[bytes]:
    done_chunk = sse_done_chunk()
    if classified.reason == StreamTerminationReason.CLOSED:
        try:
            finalize_openai_stream_frames(state)
        except OpenAIStreamAbortRequested as exception:
            async for chunk in send_error(exception.message, exception.error_type):
                yield chunk
            return
        if state.done_marker_observed:
            if state.stream_transcript is not None:
                state.stream_transcript.finalize()
                if stream_result_state is not None:
                    stream_result_state.payload = state.stream_transcript.build_result_payload()
            for usage_chunk in iter_public_usage_chunk(
                state,
                include_usage=include_usage,
                model=model,
                reported_usage=None,
            ):
                yield usage_chunk
            if emit_done_marker and not state.is_done_sent:
                yield done_chunk
                state.is_done_sent = True
            return
        state.is_stream_successful = False
        message = classified.message or "Stream terminated before completion."
        async for chunk in send_error(message, classified.error_code or "server_error"):
            yield chunk
        return
    state.is_stream_successful = False
    if classified.message is not None:
        async for chunk in send_error(classified.message, classified.error_code or "server_error"):
            yield chunk


async def iter_task_complete_chunks(
    event: TaskCompleteEvent,
    state: OpenAIStreamRuntimeState,
    *,
    emit_done_marker: bool,
    send_error: Callable[[str, str], AsyncGenerator[bytes]],
    stream_result_state: StreamGeneratorStateProtocol | None,
    include_usage: bool,
    model: str | None,
) -> AsyncGenerator[bytes]:
    done_chunk = sse_done_chunk()
    if not event.success:
        state.is_stream_successful = False
        if event.status == TaskStatus.CANCELLED.value:
            message = "Request cancelled."
            error_type = "cancelled"
        else:
            message = event.error_message or event.message or "Streaming task failed."
            error_type = (
                resolve_openai_error_type_for_http_status(event.error_code)
                if event.error_code is not None
                else "server_error"
            )
        async for chunk in send_error(message, error_type):
            yield chunk
    if event.success and state.is_stream_successful:
        try:
            finalize_openai_stream_frames(state)
        except OpenAIStreamAbortRequested as exception:
            async for chunk in send_error(exception.message, exception.error_type):
                yield chunk
        else:
            if state.stream_transcript is not None:
                state.stream_transcript.finalize()
                if stream_result_state is not None:
                    stream_result_state.payload = state.stream_transcript.build_result_payload()
            for usage_chunk in iter_public_usage_chunk(
                state,
                include_usage=include_usage,
                model=model,
                reported_usage=None,
            ):
                yield usage_chunk
    if emit_done_marker and not state.is_done_sent:
        yield done_chunk
        state.is_done_sent = True


async def iter_error_event_chunks(
    event: ErrorEvent,
    state: OpenAIStreamRuntimeState,
    *,
    send_error: Callable[[str, str], AsyncGenerator[bytes]],
    emit_done_marker: bool = True,
) -> AsyncGenerator[bytes]:
    state.is_stream_successful = False
    public_error = event.public_error
    if public_error is not None:
        status_code = public_error.http_status or error_type_to_status_code(event.error_type)
        canonical_error_type = resolve_openai_error_type_for_http_status(status_code)
        yield format_openai_sse_bytes(
            build_openai_error_payload(
                message=public_error.message,
                error_type=canonical_error_type,
                param=public_error.param,
                code=normalize_openai_error_code_subtype(
                    code=str(public_error.code), canonical_error_type=canonical_error_type
                ),
            )
        )
        if emit_done_marker and not state.is_done_sent:
            yield sse_done_chunk()
            state.is_done_sent = True
        return
    status_code = error_type_to_status_code(event.error_type)
    canonical_error_type = resolve_openai_error_type_for_http_status(int(status_code))
    error_message = event.message or "Streaming request failed."
    async for chunk in send_error(str(error_message), str(canonical_error_type)):
        yield chunk
