"""SoAI - WebSocket chat stream start cleanup policy [backend/features/api/routes/system/events/chat_stream/start_pipeline_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.conversation_publication import (
    publish_conversation_updated_and_message_saved,
)
from features.api.runtime.chat_execution.runtime_quota import (
    release_ws_chat_stream_runtime_quota_if_present,
)
from features.api.runtime.quota_reservation_finalization import (
    release_quota_reservation_required,
)
from features.assistant_timeline.models import AssistantTimelineRuntime

if TYPE_CHECKING:
    from core.conversations.conversation_message_write_result import (
        ConversationMessageWriteResult,
    )
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "OPERATION_WEBUI_WS_CHAT_STREAM_START_CLEANUP_RELEASE_QUOTA",
    "cleanup_failed_ws_chat_stream_start_noncritical",
    "cleanup_registered_ws_chat_stream_start_noncritical",
)

OPERATION_WEBUI_WS_CHAT_STREAM_START_CLEANUP_CONNECTION_STATE = (
    "webui_ws_chat_stream.start.cleanup.connection_state"
)
OPERATION_WEBUI_WS_CHAT_STREAM_START_CLEANUP_DELETE_EVENTS = (
    "webui_ws_chat_stream.start.cleanup.delete_events"
)
OPERATION_WEBUI_WS_CHAT_STREAM_START_CLEANUP_DELETE_PLACEHOLDER = (
    "webui_ws_chat_stream.start.cleanup.delete_placeholder"
)
OPERATION_WEBUI_WS_CHAT_STREAM_START_CLEANUP_REGISTRY = (
    "webui_ws_chat_stream.start.cleanup.registry"
)
OPERATION_WEBUI_WS_CHAT_STREAM_START_CLEANUP_RELEASE_QUOTA = (
    "webui_ws_chat_stream.start.cleanup.release_quota"
)
START_CLEANUP_EXCEPTIONS: tuple[type[Exception], ...] = (SoAIError, *RECOVERABLE_EXCEPTIONS)


def _log_quota_cleanup_failure(
    *,
    logger: LoggerProtocol,
    exception: Exception,
    trace_id: str | None,
    operation: str,
    conv_id: str,
    request_id: str,
) -> None:
    log_handled_exception(
        logger,
        exception,
        message="Failed to release failed chat stream quota reservation (non-critical).",
        trace_id=trace_id,
        operation=operation,
        level="warning",
        details={"conv_id": conv_id, "request_id": request_id},
    )


async def cleanup_failed_ws_chat_stream_start_noncritical(
    *,
    logger: LoggerProtocol,
    trace_id: str | None,
    api_context: ApiContext,
    chat_streams: MutableMapping[str, AssistantTimelineRuntime],
    runtime: AssistantTimelineRuntime | None,
    conv_id: str,
    request_id: str,
    placeholder_persisted: bool,
    quota_key_id: str | None,
    quota_token_reservation: JSONDict | None,
    quota_release_operation: str,
    remove_connection_state: bool,
    remove_registry: bool,
    release_quota: bool,
) -> None:
    database_messages = api_context.dependencies.webui_manager.database_messages
    if remove_connection_state and runtime is not None:
        try:
            existing = chat_streams.get(conv_id)
            if existing is runtime:
                del chat_streams[conv_id]
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to remove failed chat stream from connection state (non-critical).",
                trace_id=trace_id,
                operation=OPERATION_WEBUI_WS_CHAT_STREAM_START_CLEANUP_CONNECTION_STATE,
                level="debug",
                details={"conv_id": conv_id, "request_id": request_id},
            )
    if remove_registry and runtime is not None:
        try:
            await api_context.dependencies.chat_stream_registry.remove_if_same(runtime)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to remove failed chat stream from global registry (non-critical).",
                trace_id=trace_id,
                operation=OPERATION_WEBUI_WS_CHAT_STREAM_START_CLEANUP_REGISTRY,
                level="debug",
                details={"conv_id": conv_id, "request_id": request_id},
            )
    if release_quota and runtime is not None:
        try:
            await release_ws_chat_stream_runtime_quota_if_present(
                database_api_keys=api_context.dependencies.webui_manager.database_api_keys,
                runtime=runtime,
                trace_id=trace_id,
                operation=quota_release_operation,
            )
        except START_CLEANUP_EXCEPTIONS as exception:
            _log_quota_cleanup_failure(
                logger=logger,
                exception=exception,
                trace_id=trace_id,
                operation=quota_release_operation,
                conv_id=conv_id,
                request_id=request_id,
            )
    elif release_quota and quota_key_id is not None and quota_token_reservation is not None:
        try:
            await release_quota_reservation_required(
                database_api_keys=api_context.dependencies.webui_manager.database_api_keys,
                key_id=quota_key_id,
                reservation=quota_token_reservation,
                trace_id=trace_id,
                operation=quota_release_operation,
            )
        except START_CLEANUP_EXCEPTIONS as exception:
            _log_quota_cleanup_failure(
                logger=logger,
                exception=exception,
                trace_id=trace_id,
                operation=quota_release_operation,
                conv_id=conv_id,
                request_id=request_id,
            )
    if placeholder_persisted and runtime is not None:
        cleanup_write_result: ConversationMessageWriteResult | None = None
        try:
            cleanup_write_result = await database_messages.delete_streaming_assistant_events(
                conv_id,
                runtime.user_id,
                assistant_at_ms=runtime.assistant_at_ms,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to delete streaming assistant events after chat start failure (non-critical).",
                trace_id=trace_id,
                operation=OPERATION_WEBUI_WS_CHAT_STREAM_START_CLEANUP_DELETE_EVENTS,
                level="debug",
                details={"conv_id": conv_id, "request_id": request_id},
            )
        try:
            cleanup_write_result = await database_messages.delete_streaming_assistant_message(
                conv_id,
                runtime.user_id,
                created_at_ms=runtime.assistant_at_ms,
            )
            runtime.assistant_placeholder_persisted = False
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to delete streaming assistant placeholder after chat start failure (non-critical).",
                trace_id=trace_id,
                operation=OPERATION_WEBUI_WS_CHAT_STREAM_START_CLEANUP_DELETE_PLACEHOLDER,
                level="debug",
                details={"conv_id": conv_id, "request_id": request_id},
            )
        if cleanup_write_result is not None:
            try:
                await publish_conversation_updated_and_message_saved(
                    api_context.dependencies.event_bus,
                    user_id=runtime.user_id,
                    conv_id=conv_id,
                    message_count=cleanup_write_result.message_count,
                    last_modified_at_ms=cleanup_write_result.last_modified_at_ms,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to publish chat start cleanup message update (non-critical).",
                    trace_id=trace_id,
                    operation=OPERATION_WEBUI_WS_CHAT_STREAM_START_CLEANUP_DELETE_PLACEHOLDER,
                    level="debug",
                    details={"conv_id": conv_id, "request_id": request_id},
                )


async def cleanup_registered_ws_chat_stream_start_noncritical(
    *,
    logger: LoggerProtocol,
    trace_id: str | None,
    api_context: ApiContext,
    chat_streams: MutableMapping[str, AssistantTimelineRuntime],
    runtime: AssistantTimelineRuntime,
    delete_placeholder: bool,
    release_quota: bool,
) -> None:
    await uncancel_then_cleanup(
        cleanup_failed_ws_chat_stream_start_noncritical(
            logger=logger,
            trace_id=trace_id,
            api_context=api_context,
            chat_streams=chat_streams,
            runtime=runtime,
            conv_id=runtime.conv_id,
            request_id=runtime.request_id,
            placeholder_persisted=delete_placeholder,
            quota_key_id=runtime.quota_key_id,
            quota_token_reservation=runtime.quota_token_reservation,
            quota_release_operation=OPERATION_WEBUI_WS_CHAT_STREAM_START_CLEANUP_RELEASE_QUOTA,
            remove_connection_state=True,
            remove_registry=True,
            release_quota=release_quota,
        ),
    )
