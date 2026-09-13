"""SoAI - OpenAI-compatible SSE streaming response generator [backend/features/api/streaming/openai_stream_generator/generator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.openai.sse_events import format_openai_stream_error_chunk
from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
from core.openai.sse_frames import sse_done_chunk
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.openai.streaming_token_budget import build_streaming_token_budget
from core.runtime.request_context import RequestContext
from core.streaming.protocols import StreamGeneratorStateProtocol
from features.api.streaming.internal_protocols import (
    OpenAIStreamApiDependenciesProtocol,
)
from features.api.streaming.openai_stream_generator.event_loop import (
    run_stream_event_loop,
)
from features.api.streaming.openai_stream_generator.finalization import finalize_stream
from features.api.streaming.openai_stream_generator.runtime_state import (
    OpenAIStreamRuntimeState,
)
from features.api.streaming.stream_cancel import schedule_streaming_task_cancel
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("create_stream_generator",)

LOGGER_NAME = "SoAI.features.api.openai_stream_generator_generator"
OPERATION = "api_streaming.create_stream_generator"


async def create_stream_generator(
    reply_queue: asyncio.Queue[Event],
    stream_dependencies: StreamDependencies,
    api_dependencies: OpenAIStreamApiDependenciesProtocol,
    context: RequestContext,
    *,
    format_error_chunk: Callable[[str, str, str], str] | None = None,
    task_id: str | None = None,
    stream_transcript: OpenAIStreamTranscript | None = None,
    model: str | None = None,
    stream_object_hint: str | None = None,
    emit_done_marker: bool = True,
    schedule_tool_calls: bool = True,
    stream_result_state: StreamGeneratorStateProtocol | None = None,
    include_usage: bool = False,
    quota_reservation: JSONDict | None = None,
    quota_prompt_tokens: int | None = None,
    allow_image_events: bool = False,
    collect_tool_calls: bool = True,
) -> AsyncGenerator[bytes]:
    logger = get_logger(LOGGER_NAME)
    done_chunk = sse_done_chunk()
    try:
        trace_id_value = context.trace_id
    except AttributeError:
        trace_id_value = None
    trace_id = str(trace_id_value or "").strip() or "no-trace"
    resolved_task_id: str | None
    if task_id is not None:
        resolved_task_id = task_id
    else:
        try:
            resolved_task_id = context.task_id
        except AttributeError:
            resolved_task_id = None
    try:
        resolved_user_id = context.user_id
    except AttributeError:
        resolved_user_id = None
    if isinstance(resolved_task_id, str) and resolved_task_id:
        try:
            resolved_user_id_int = (
                0 if isinstance(resolved_user_id, bool) else int(resolved_user_id or 0)
            )
        except (TypeError, ValueError):
            resolved_user_id_int = 0
        stream_dependencies.task_registry.bind_reply_queue_identity(
            reply_queue,
            task_id=resolved_task_id,
            user_id=resolved_user_id_int,
        )
    resolved_transcript = stream_transcript
    resolved_collect_tool_calls = collect_tool_calls
    if resolved_transcript is not None:
        resolved_collect_tool_calls = resolved_transcript.collects_tool_calls()
    resolved_schedule_tool_calls = schedule_tool_calls and resolved_collect_tool_calls
    if resolved_transcript is None and (
        resolved_schedule_tool_calls or stream_result_state is not None
    ):
        resolved_transcript = OpenAIStreamTranscript(
            model_hint=model,
            collect_tool_calls=resolved_collect_tool_calls,
        )
    token_budget = None
    if quota_reservation is not None:
        token_budget = build_streaming_token_budget(
            quota_reservation,
            quota_prompt_tokens,
            stream_dependencies.config,
            stream_dependencies.prompt_token_counter,
            model_name=model,
        )
    state = OpenAIStreamRuntimeState(
        is_done_sent=False,
        is_stream_successful=True,
        abort_stream=False,
        cancel_scheduled=False,
        done_marker_observed=False,
        chunk_accumulator=OpenAISSEFrameAccumulator(),
        stream_transcript=resolved_transcript,
        stream_id=None,
        stream_object=stream_object_hint,
        quota_completion_token_budget=token_budget,
        collect_tool_calls=resolved_collect_tool_calls,
        tool_call_ids_by_index={},
        tool_call_ids_by_ordinal={},
    )

    def schedule_task_cancel(reason: str) -> None:
        if state.cancel_scheduled:
            return
        if not isinstance(resolved_task_id, str) or not resolved_task_id:
            return
        state.cancel_scheduled = True
        scheduled = schedule_streaming_task_cancel(
            stream_dependencies.task_registry,
            resolved_task_id,
            reason,
            context,
            logger,
            "api_streaming.create_stream_generator.schedule_task_cancel",
            api_dependencies.application_control.track_background_task,
        )
        if not scheduled:
            state.cancel_scheduled = False

    async def send_error(message: str, error_type: str) -> AsyncGenerator[bytes]:
        error_bytes = format_openai_stream_error_chunk(
            format_error_chunk,
            message,
            error_type,
            trace_id,
        )
        yield error_bytes
        if emit_done_marker and not state.is_done_sent:
            yield done_chunk
            state.is_done_sent = True

    logger.debug("[%s] Starting OpenAI stream generator.", trace_id)
    try:
        async for stream_bytes in run_stream_event_loop(
            reply_queue,
            stream_dependencies,
            context,
            state=state,
            trace_id=trace_id,
            logger=logger,
            send_error=send_error,
            schedule_task_cancel=schedule_task_cancel,
            model=model,
            emit_done_marker=emit_done_marker,
            stream_result_state=stream_result_state,
            include_usage=include_usage,
            allow_image_events=allow_image_events,
        ):
            yield stream_bytes
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        state.is_stream_successful = False
        log_exception(
            logger,
            exception,
            message="Unhandled streaming error in OpenAI stream generator.",
            trace_id=trace_id,
            operation=OPERATION,
        )
        async for chunk in send_error(
            "An unexpected server error occurred in the stream generator.",
            "server_error",
        ):
            yield chunk
    finally:
        await uncancel_then_cleanup(
            finalize_stream(
                state,
                stream_result_state=stream_result_state,
                schedule_tool_calls=resolved_schedule_tool_calls,
                api_dependencies=api_dependencies,
                context=context,
                logger=logger,
                trace_id=trace_id,
            ),
        )
