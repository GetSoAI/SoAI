"""SoAI - Durable chat stream start failure finalization [backend/features/api/routes/system/events/chat_stream/start_failure_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.cancellation_ids import build_chat_stream_task_cancellation_id
from core.runtime.soai_identifiers import create_system_id
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.assistant_placeholder_publication import (
    persist_streaming_assistant_placeholder,
)
from features.assistant_timeline.conversation_events import (
    publish_chat_stream_message_events,
)
from features.assistant_timeline.loading_error_finalization import (
    finalize_and_publish_loading_error,
)
from features.assistant_timeline.runtime_construction import create_chat_stream_runtime

if TYPE_CHECKING:
    from core.conversations.assistant_turn_variant_identity import (
        AssistantTurnVariantIdentity,
    )
    from core.events.protocols import EventBusProtocol
    from core.runtime.protocols import RequestProtocol
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.api.streaming.websocket import WebsocketConnection
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "ChatStreamStartFailureBoundary",
    "ChatStreamStartFailureContext",
    "build_chat_stream_start_failure_context",
    "create_start_failure_runtime",
    "finalize_chat_stream_start_failure",
    "finalize_existing_chat_stream_start_failure",
)

LOGGER_NAME = "SoAI.features.api.start_failure_finalization"
OPERATION_START_FAILURE_MESSAGE_EVENTS = "webui_ws_chat_stream.start_failure.message_events"
START_FAILURE_MESSAGE_EVENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    *RECOVERABLE_EXCEPTIONS,
)


@dataclass(frozen=True, slots=True)
class ChatStreamStartFailureBoundary:
    request: RequestProtocol
    api_context: ApiContext
    stream_dependencies: StreamDependencies
    connection: WebsocketConnection
    conv_id: str
    request_id: str
    user_id: int
    model_id: str | None


@dataclass(frozen=True, slots=True)
class ChatStreamStartFailureContext:
    boundary: ChatStreamStartFailureBoundary
    identity: AssistantTurnVariantIdentity
    message_index: int


def build_chat_stream_start_failure_context(
    *,
    boundary: ChatStreamStartFailureBoundary,
    identity: AssistantTurnVariantIdentity,
    message_index: int,
) -> ChatStreamStartFailureContext:
    return ChatStreamStartFailureContext(
        boundary=boundary,
        identity=identity,
        message_index=message_index,
    )


def _context_cancellation_id(request: RequestProtocol) -> str:
    try:
        value = request.state.context.cancellation_id
    except AttributeError:
        return ""
    return value.strip() if isinstance(value, str) else ""


def _task_cancellation_id(*, request: RequestProtocol, request_id: str) -> str:
    try:
        cancellation_id = build_chat_stream_task_cancellation_id(
            context_cancellation_id=_context_cancellation_id(request),
            request_id=request_id,
        )
    except ValidationError:
        cancellation_id = create_system_id(
            subsystem="ws_chat_stream",
            owner="start_failed",
            include_random_suffix=True,
        )
    return cancellation_id


def create_start_failure_runtime(
    *,
    request: RequestProtocol,
    conv_id: str,
    request_id: str,
    identity: AssistantTurnVariantIdentity,
    user_id: int,
    message_index: int,
    model_id: str | None,
) -> AssistantTimelineRuntime:
    return create_chat_stream_runtime(
        conv_id=conv_id,
        request_id=request_id,
        identity=identity,
        user_id=user_id,
        message_index=message_index,
        model_id=model_id,
        task_cancellation_id=_task_cancellation_id(request=request, request_id=request_id),
        started_at_monotonic_ms=int(monotonic_ms()),
    )


async def _publish_start_failure_message_events(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
) -> None:
    try:
        await publish_chat_stream_message_events(
            event_bus,
            runtime,
        )
    except START_FAILURE_MESSAGE_EVENT_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to publish chat stream start-failure final message events (non-critical).",
            operation=OPERATION_START_FAILURE_MESSAGE_EVENTS,
            level="warning",
            details={
                "conv_id": runtime.conv_id,
                "request_id": runtime.request_id,
            },
        )


async def finalize_chat_stream_start_failure(
    *,
    context: ChatStreamStartFailureContext,
    error_code: str,
    error_message: str,
) -> None:
    runtime = create_start_failure_runtime(
        request=context.boundary.request,
        conv_id=context.boundary.conv_id,
        request_id=context.boundary.request_id,
        identity=context.identity,
        user_id=context.boundary.user_id,
        message_index=context.message_index,
        model_id=context.boundary.model_id,
    )
    await persist_streaming_assistant_placeholder(
        database_messages=context.boundary.api_context.dependencies.webui_manager.database_messages,
        runtime=runtime,
    )
    await finalize_and_publish_loading_error(
        runtime=runtime,
        event_bus=context.boundary.stream_dependencies.event_bus,
        database_messages=context.boundary.api_context.dependencies.webui_manager.database_messages,
        duration_ms=0,
        thinking_tail_duration_ms=0,
        message=error_message,
        code=error_code,
    )
    await _publish_start_failure_message_events(
        event_bus=context.boundary.stream_dependencies.event_bus,
        runtime=runtime,
    )


async def finalize_existing_chat_stream_start_failure(
    *,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    runtime: AssistantTimelineRuntime,
    placeholder_persisted: bool,
    error_code: str,
    error_message: str,
) -> None:
    if not placeholder_persisted:
        await persist_streaming_assistant_placeholder(
            database_messages=api_context.dependencies.webui_manager.database_messages,
            runtime=runtime,
        )
    await finalize_and_publish_loading_error(
        runtime=runtime,
        event_bus=stream_dependencies.event_bus,
        database_messages=api_context.dependencies.webui_manager.database_messages,
        duration_ms=0,
        thinking_tail_duration_ms=0,
        message=error_message,
        code=error_code,
    )
    await _publish_start_failure_message_events(
        event_bus=stream_dependencies.event_bus,
        runtime=runtime,
    )
