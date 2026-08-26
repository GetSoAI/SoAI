"""SoAI - OpenAI stream generator finalization logic [backend/features/api/streaming/openai_stream_generator/finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_waiting import (
    EventPublicationReceipt,
    publication_completion_deadline,
)
from core.events.types_system import ThinkingTailCompletedEvent
from core.logging.protocols import LoggerProtocol
from core.runtime.request_context import RequestContext
from core.streaming.protocols import StreamGeneratorStateProtocol
from core.validation.integers import is_strict_int
from features.api.streaming.internal_protocols import (
    OpenAIStreamApiDependenciesProtocol,
)
from features.api.streaming.openai_stream_generator.runtime_state import (
    OpenAIStreamRuntimeState,
)

__all__ = ("finalize_stream",)

OPERATION_API_STREAMING_CREATE_STREAM_GENERATOR_FINALIZE_TRANSCRIPT = (
    "api_streaming.create_stream_generator.finalize_transcript"
)
OPERATION_API_STREAMING_CREATE_STREAM_GENERATOR_PUBLISH_THINKING_TAIL_COMPLETED = (
    "api_streaming.create_stream_generator.publish_thinking_tail_completed"
)


async def finalize_stream(
    state: OpenAIStreamRuntimeState,
    *,
    stream_result_state: StreamGeneratorStateProtocol | None,
    schedule_tool_calls: bool,
    api_dependencies: OpenAIStreamApiDependenciesProtocol,
    context: RequestContext,
    logger: LoggerProtocol,
    trace_id: str,
) -> None:
    transcript = state.stream_transcript
    if transcript is not None:
        try:
            transcript.finalize()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to finalize OpenAI stream transcript (non-critical).",
                trace_id=trace_id,
                operation=OPERATION_API_STREAMING_CREATE_STREAM_GENERATOR_FINALIZE_TRANSCRIPT,
                level="debug",
            )
    if stream_result_state is not None:
        stream_result_state.done_sent = state.is_done_sent
        stream_result_state.stream_successful = state.is_stream_successful
        if (
            transcript is not None
            and state.is_stream_successful
            and stream_result_state.payload is None
        ):
            stream_result_state.payload = transcript.build_result_payload()
        if (
            transcript is not None
            and not state.is_stream_successful
            and stream_result_state.payload is None
            and stream_result_state.partial_payload is None
        ):
            stream_result_state.partial_payload = transcript.build_result_payload()
    timeline_tail_duration_ms = (
        transcript.get_thinking_tail_duration_ms() if transcript is not None else None
    )
    if transcript is None or not state.is_stream_successful:
        return
    try:
        tool_context = context.mcp_tool_context
    except AttributeError:
        tool_context = None
    if tool_context is not None:
        try:
            conv_id_value = tool_context.conv_id
        except AttributeError:
            conv_id_value = ""
        conv_id = str(conv_id_value or "").strip()
        try:
            user_id_value = tool_context.user_id
        except AttributeError:
            user_id_value = None
        try:
            message_index_value = tool_context.message_index
        except AttributeError:
            message_index_value = None
        user_id: int | None = None
        if is_strict_int(user_id_value) and user_id_value >= 0:
            user_id = user_id_value
        message_index: int | None = None
        if is_strict_int(message_index_value) and message_index_value >= 0:
            message_index = message_index_value
        tail_duration: int | None = None
        if isinstance(timeline_tail_duration_ms, int) and timeline_tail_duration_ms >= 0:
            tail_duration = timeline_tail_duration_ms
        if (
            user_id is not None
            and message_index is not None
            and conv_id
            and tail_duration is not None
        ):
            try:
                event = ThinkingTailCompletedEvent(
                    user_id=user_id,
                    conv_id=conv_id,
                    message_index=message_index,
                    duration_ms=tail_duration,
                )
                receipt = EventPublicationReceipt.create(
                    event_type=type(event).__name__,
                    operation="api_streaming.create_stream_generator.publish_thinking_tail_completed",
                )
                await api_dependencies.event_bus.publish(
                    event,
                    wait_for_completion=receipt.completion_signal,
                )
                await receipt.wait_for_completion(publication_completion_deadline())
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to publish thinking tail completion event (non-critical).",
                    trace_id=trace_id,
                    operation=OPERATION_API_STREAMING_CREATE_STREAM_GENERATOR_PUBLISH_THINKING_TAIL_COMPLETED,
                    level="debug",
                )
    if not schedule_tool_calls:
        return
    tool_calls = transcript.get_tool_calls()
    if not tool_calls:
        return
    api_dependencies.tool_call_processor.schedule_tool_call_processing(
        request_context=context,
        raw_tool_calls=tool_calls,
        logger=logger,
        track_background_task=api_dependencies.application_control.track_background_task,
    )
