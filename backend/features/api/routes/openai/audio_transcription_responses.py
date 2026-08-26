"""SoAI - OpenAI transcription response negotiation [backend/features/api/routes/openai/audio_transcription_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Never

from fastapi import Request
from starlette.responses import Response

from core.errors.exceptions import StateError
from core.errors.status_mapping import error_type_to_status_code
from core.events.types_models_streaming import (
    InferenceResultEvent,
    StreamChunkEvent,
    StreamEndEvent,
)
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent, TaskProgressEvent
from core.files.upload_staging import cleanup_temp_files
from core.openai.sse_events import format_openai_stream_error_chunk
from core.openai.sse_frames import sse_keepalive_chunk
from core.tasks.finalization import finalize
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response_for_status,
)
from features.api.runtime.response_collection import process_command_reply
from features.api.runtime.response_terminal_events import (
    handle_inference_result_event,
    handle_task_complete_event,
)
from features.api.runtime.responses import (
    build_task_operation_headers,
    create_json_response_with_task_id,
)
from features.api.streaming.sse_responses import create_sse_response
from features.api.streaming.stream_dependencies import build_stream_dependencies
from features.api.streaming.stream_iteration import (
    StreamEvent,
    StreamKeepalive,
    StreamTermination,
    iter_classified_stream_events,
)

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.types.json import JSONValue
    from features.api.runtime.context import ApiContext

__all__ = ("negotiate_audio_transcription_response",)


async def negotiate_audio_transcription_response(
    request: Request,
    *,
    api_context: ApiContext,
    task_id: str,
    reply_queue: asyncio.Queue[Event],
    command_fields: dict[str, JSONValue],
    staged_paths: tuple[str, ...],
) -> Response:
    stream_owns_cleanup = False
    classified_iter: (
        AsyncGenerator[
            StreamKeepalive | StreamEvent[Event] | StreamTermination,
            None,
        ]
        | None
    ) = None
    try:
        stream_dependencies = build_stream_dependencies(api_context.dependencies)
        classified_iter = iter_classified_stream_events(
            reply_queue,
            stream_dependencies,
            request.state.context,
            publish_cancel_command=True,
            close_on_timeout=True,
        )
        async for classified in classified_iter:
            if isinstance(classified, StreamKeepalive):
                continue
            if isinstance(classified, StreamTermination):
                _raise_pre_stream_termination(classified)
            event = classified.event
            if isinstance(event, StreamChunkEvent):
                streaming_response = create_sse_response(
                    _stream_transcription_events(
                        classified_iter,
                        first_chunk=event.chunk,
                        staged_paths=staged_paths,
                        trace_id=request.state.context.trace_id,
                    ),
                    additional_headers=build_task_operation_headers(
                        task_id=task_id,
                        operation_id=request.state.context.trace_id,
                    ),
                )
                stream_owns_cleanup = True
                return streaming_response
            if isinstance(event, InferenceResultEvent):
                return await handle_inference_result_event(
                    request,
                    api_context.dependencies.task_registry,
                    event,
                    process_command_reply=process_command_reply,
                    finalize_task=finalize,
                    json_response_with_task_id=create_json_response_with_task_id,
                    task_id=task_id,
                    command_fields=command_fields,
                )
            if isinstance(event, TaskCompleteEvent):
                return await handle_task_complete_event(
                    request,
                    event,
                    process_command_reply=process_command_reply,
                    json_response_with_task_id=create_json_response_with_task_id,
                    task_id=task_id,
                )
            if isinstance(event, ErrorEvent):
                return build_openai_error_json_response_for_status(
                    status_code=error_type_to_status_code(event.error_type),
                    message=event.message or "Transcription request failed.",
                    soai_code=event.error_type.value,
                    param=None,
                    trace_id=request.state.context.trace_id,
                    headers=build_task_operation_headers(
                        task_id=task_id,
                        operation_id=request.state.context.trace_id,
                    ),
                    message_is_public=True,
                )
            if isinstance(event, StreamEndEvent):
                raise StateError("Transcription stream ended before emitting an SSE event.")
            if isinstance(event, TaskProgressEvent):
                continue
        raise StateError("Transcription response channel closed without a response.")
    finally:
        if not stream_owns_cleanup:
            if classified_iter is not None:
                await classified_iter.aclose()
            await cleanup_temp_files(staged_paths)


async def _stream_transcription_events(
    classified_iter: AsyncGenerator[StreamKeepalive | StreamEvent[Event] | StreamTermination],
    *,
    first_chunk: bytes,
    staged_paths: tuple[str, ...],
    trace_id: str | None,
) -> AsyncGenerator[bytes]:
    try:
        yield first_chunk
        async for classified in classified_iter:
            if isinstance(classified, StreamKeepalive):
                yield sse_keepalive_chunk()
                continue
            if isinstance(classified, StreamTermination):
                yield _format_stream_error(
                    classified.message or "Transcription stream terminated.",
                    classified.error_code or "server_error",
                    trace_id,
                )
                break
            event = classified.event
            if isinstance(event, StreamChunkEvent):
                yield event.chunk
                continue
            if isinstance(event, StreamEndEvent):
                break
            if isinstance(event, ErrorEvent):
                yield _format_stream_error(
                    event.message or "Transcription stream failed.",
                    event.error_type.value,
                    trace_id,
                )
                break
            if isinstance(event, TaskCompleteEvent):
                if not event.success:
                    yield _format_stream_error(
                        event.error_message or event.message or "Transcription stream failed.",
                        "server_error",
                        trace_id,
                    )
                break
            if isinstance(event, InferenceResultEvent):
                yield _format_stream_error(
                    "Transcription provider changed response modes after streaming began.",
                    "invalid_stream_error",
                    trace_id,
                )
                break
            if isinstance(event, TaskProgressEvent):
                continue
    finally:
        await classified_iter.aclose()
        await cleanup_temp_files(staged_paths)


def _format_stream_error(message: str, error_type: str, trace_id: str | None) -> bytes:
    return format_openai_stream_error_chunk(
        None,
        message,
        error_type,
        trace_id or "no-trace",
    )


def _raise_pre_stream_termination(termination: StreamTermination) -> Never:
    if termination.error_code == "timeout_error":
        raise TimeoutError(termination.message or "Transcription stream timed out.")
    raise StateError(termination.message or "Transcription stream closed before starting.")
