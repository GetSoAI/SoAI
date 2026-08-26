"""SoAI - Automation chat stream runtime lifecycle [backend/features/automation/execution_stream_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.conversation_publication import (
    publish_conversation_updated_and_message_saved,
)
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from core.conversations.conversation_message_write_result import (
        ConversationMessageWriteResult,
    )
    from features.api.runtime.container.types import ApiDependencies
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "cleanup_failed_automation_stream_reservation",
    "register_automation_stream_runtime",
    "release_automation_stream_runtime",
)

LOGGER_NAME = "SoAI.features.automation.execution_stream_lifecycle"
OPERATION_DELETE_EVENTS = "automation.execution_stream_lifecycle.delete_events"
OPERATION_DELETE_PLACEHOLDER = "automation.execution_stream_lifecycle.delete_placeholder"
OPERATION_PUBLISH_CLEANUP = "automation.execution_stream_lifecycle.publish_cleanup"


async def register_automation_stream_runtime(
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
) -> None:
    registered = await api_dependencies.chat_stream_registry.try_register(runtime)
    if not registered:
        raise StateError("Automation turn stream runtime registration failed.")


async def release_automation_stream_runtime(
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
) -> None:
    await uncancel_then_cleanup(api_dependencies.chat_stream_registry.remove_if_same(runtime))


async def cleanup_failed_automation_stream_reservation(
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
) -> None:
    cleanup_write_result: ConversationMessageWriteResult | None = None
    try:
        if runtime.latest_message_write_count is not None:
            cleanup_write_result = (
                await api_dependencies.database_messages.delete_streaming_assistant_events(
                    runtime.conv_id,
                    runtime.user_id,
                    assistant_at_ms=runtime.assistant_at_ms,
                )
            )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to delete automation assistant stream events after reservation failure.",
            operation=OPERATION_DELETE_EVENTS,
            level="debug",
            details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
        )
    try:
        if runtime.latest_message_write_count is not None:
            cleanup_write_result = (
                await api_dependencies.database_messages.delete_streaming_assistant_message(
                    runtime.conv_id,
                    runtime.user_id,
                    created_at_ms=runtime.assistant_at_ms,
                )
            )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to delete automation assistant placeholder after reservation failure.",
            operation=OPERATION_DELETE_PLACEHOLDER,
            level="debug",
            details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
        )
    await release_automation_stream_runtime(api_dependencies, runtime)
    if cleanup_write_result is None:
        return
    try:
        await publish_conversation_updated_and_message_saved(
            api_dependencies.event_bus,
            user_id=runtime.user_id,
            conv_id=runtime.conv_id,
            message_count=cleanup_write_result.message_count,
            last_modified_at_ms=cleanup_write_result.last_modified_at_ms,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to publish automation assistant reservation cleanup update.",
            operation=OPERATION_PUBLISH_CLEANUP,
            level="debug",
            details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
        )
