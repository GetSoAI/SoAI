"""SoAI - OpenAI stream generator event loop [backend/features/api/streaming/openai_stream_generator/event_loop.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import TYPE_CHECKING

from core.events.types_base import Event
from core.events.types_models_streaming import StreamChunkEvent, StreamEndEvent
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent, TaskProgressEvent
from core.openai.sse_frames import sse_keepalive_chunk
from features.api.streaming.openai_stream_generator.chunk_event_processing import (
    iter_stream_bytes_from_chunk_event,
)
from features.api.streaming.openai_stream_generator.end_event_processing import (
    iter_stream_bytes_from_end_event,
)
from features.api.streaming.openai_stream_generator.event_loop_terminal_events import (
    iter_error_event_chunks,
    iter_task_complete_chunks,
    iter_termination_chunks,
)
from features.api.streaming.openai_stream_generator.stream_abort import (
    OpenAIStreamAbortRequested,
)
from features.api.streaming.stream_iteration import (
    StreamTermination,
    iter_openai_sse_classified_stream_events_with_keepalive_chunks,
)

if TYPE_CHECKING:
    import asyncio

    from core.logging.protocols import TraceLogger
    from core.runtime.request_context import RequestContext
    from core.streaming.protocols import StreamGeneratorStateProtocol
    from features.api.streaming.openai_stream_generator.runtime_state import (
        OpenAIStreamRuntimeState,
    )
    from features.api.streaming.types import StreamDependencies

__all__ = ("run_stream_event_loop",)


async def run_stream_event_loop(
    reply_queue: asyncio.Queue[Event],
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    *,
    state: OpenAIStreamRuntimeState,
    trace_id: str,
    logger: TraceLogger,
    send_error: Callable[[str, str], AsyncGenerator[bytes]],
    schedule_task_cancel: Callable[[str], None],
    model: str | None,
    emit_done_marker: bool,
    stream_result_state: StreamGeneratorStateProtocol | None,
    include_usage: bool,
    allow_image_events: bool,
) -> AsyncGenerator[bytes]:
    keepalive_chunk = sse_keepalive_chunk()
    async for item in iter_openai_sse_classified_stream_events_with_keepalive_chunks(
        reply_queue,
        stream_dependencies,
        context,
        keepalive_chunk=keepalive_chunk,
    ):
        if isinstance(item, bytes):
            yield item
            continue
        classified = item
        if state.abort_stream:
            break
        if isinstance(classified, StreamTermination):
            async for chunk in iter_termination_chunks(
                classified,
                state,
                emit_done_marker=emit_done_marker,
                send_error=send_error,
                stream_result_state=stream_result_state,
            ):
                yield chunk
            break
        event = classified.event
        if isinstance(event, StreamChunkEvent):
            if state.done_marker_observed:
                continue
            if not isinstance(event.chunk, bytes | bytearray | memoryview | str):
                message = "Provider returned an invalid OpenAI stream chunk type."
                logger.warning(
                    "[%s] %s %s",
                    trace_id,
                    message,
                    type(event.chunk).__name__,
                )
                state.is_stream_successful = False
                state.abort_stream = True
                schedule_task_cancel(message)
                async for chunk in send_error(message, "invalid_stream_error"):
                    yield chunk
                break
            try:
                for stream_bytes in iter_stream_bytes_from_chunk_event(
                    event,
                    state,
                    trace_id=trace_id,
                    logger=logger,
                    schedule_task_cancel=schedule_task_cancel,
                    allow_image_events=allow_image_events,
                    emit_done_marker=emit_done_marker,
                ):
                    yield stream_bytes
            except OpenAIStreamAbortRequested as exception:
                async for chunk in send_error(exception.message, exception.error_type):
                    yield chunk
                break
            continue
        if isinstance(event, StreamEndEvent):
            try:
                for stream_bytes in iter_stream_bytes_from_end_event(
                    event,
                    state,
                    include_usage=include_usage,
                    model=model,
                    emit_done_marker=emit_done_marker,
                    stream_result_state=stream_result_state,
                ):
                    yield stream_bytes
            except OpenAIStreamAbortRequested as exception:
                logger.warning("[%s] %s", trace_id, exception.message)
                async for chunk in send_error(exception.message, exception.error_type):
                    yield chunk
            break
        if isinstance(event, ErrorEvent):
            async for chunk in iter_error_event_chunks(
                event,
                state,
                send_error=send_error,
            ):
                yield chunk
            break
        if isinstance(event, TaskCompleteEvent):
            async for chunk in iter_task_complete_chunks(
                event,
                state,
                emit_done_marker=emit_done_marker,
                send_error=send_error,
                stream_result_state=stream_result_state,
            ):
                yield chunk
            break
        if isinstance(event, TaskProgressEvent):
            continue
        logger.debug(
            "[%s] Stream generator ignoring event type: %s",
            trace_id,
            type(event).__name__,
        )
