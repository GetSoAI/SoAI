"""SoAI - WebSocket Chat preparation terminalization [backend/features/api/routes/system/events/chat_stream/start_preparation_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_handled_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.timing.monotonic import monotonic_ms
from features.api.routes.system.events.chat_stream.start_failure_finalization import (
    finalize_existing_chat_stream_start_failure,
)
from features.api.routes.system.events.chat_stream.start_pipeline_cleanup import (
    cleanup_registered_ws_chat_stream_start_noncritical,
)
from features.assistant_timeline.conversation_events import (
    publish_chat_stream_message_events,
)
from features.assistant_timeline.loading_cancelled_finalization import (
    finalize_and_publish_loading_cancelled,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("finalize_preparation_cancelled", "finalize_preparation_error")

OPERATION_CANCEL_MESSAGE_EVENTS = "webui_ws_chat_stream.start.prepare_cancel_message_events"


async def finalize_preparation_error(
    *,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    chat_streams: MutableMapping[str, AssistantTimelineRuntime],
    runtime: AssistantTimelineRuntime,
    placeholder_persisted: bool,
    error_code: str,
    error_message: str,
    trace_id: str | None,
    logger: LoggerProtocol,
) -> None:
    finalized = False
    try:
        await finalize_existing_chat_stream_start_failure(
            api_context=api_context,
            stream_dependencies=stream_dependencies,
            runtime=runtime,
            placeholder_persisted=placeholder_persisted,
            error_code=error_code,
            error_message=error_message,
        )
        finalized = True
    finally:
        delete_placeholder = (
            runtime.assistant_placeholder_persisted
            and not finalized
            and not runtime.terminal_persistence_completed
        )
        await uncancel_then_cleanup(
            cleanup_registered_ws_chat_stream_start_noncritical(
                api_context=api_context,
                chat_streams=chat_streams,
                runtime=runtime,
                trace_id=trace_id,
                logger=logger,
                delete_placeholder=delete_placeholder,
                release_quota=True,
            ),
        )


async def finalize_preparation_cancelled(
    *,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    chat_streams: MutableMapping[str, AssistantTimelineRuntime],
    runtime: AssistantTimelineRuntime,
    placeholder_persisted: bool,
    trace_id: str | None,
    logger: LoggerProtocol,
) -> None:
    finalized = False
    try:
        if runtime.cancellation_requested and placeholder_persisted:
            await uncancel_then_cleanup(
                finalize_and_publish_loading_cancelled(
                    runtime=runtime,
                    event_bus=stream_dependencies.event_bus,
                    database_messages=api_context.dependencies.webui_manager.database_messages,
                    duration_ms=max(0, int(monotonic_ms()) - runtime.started_at_monotonic_ms),
                    thinking_tail_duration_ms=0,
                    reason=runtime.cancellation_reason or "Chat stream was cancelled.",
                ),
            )
            finalized = True
            if runtime.assistant_placeholder_persisted:
                try:
                    await uncancel_then_cleanup(
                        publish_chat_stream_message_events(stream_dependencies.event_bus, runtime),
                    )
                except HANDLED_RUNTIME_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Failed to publish chat stream preparation-cancel message events.",
                        trace_id=trace_id,
                        operation=OPERATION_CANCEL_MESSAGE_EVENTS,
                        level="warning",
                        details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
                    )
        elif runtime.cancellation_requested:
            await uncancel_then_cleanup(
                api_context.dependencies.database_stream_cancellations.settle_local(
                    conv_id=runtime.conv_id,
                    user_id=runtime.user_id,
                    request_id=runtime.request_id,
                ),
            )
            await uncancel_then_cleanup(
                api_context.dependencies.chat_stream_registry.clear_cancellation_intent_if_same(
                    user_id=runtime.user_id,
                    conv_id=runtime.conv_id,
                    request_id=runtime.request_id,
                ),
            )
            finalized = True
    finally:
        await cleanup_registered_ws_chat_stream_start_noncritical(
            api_context=api_context,
            chat_streams=chat_streams,
            runtime=runtime,
            trace_id=trace_id,
            logger=logger,
            delete_placeholder=(
                placeholder_persisted and not finalized and not runtime.cancellation_requested
            ),
            release_quota=True,
        )
