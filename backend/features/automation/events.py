"""SoAI - Automation event publishing helpers [backend/features/automation/events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.conversation_publication import (
    build_conversation_created_event,
    publish_conversation_updated_and_message_saved,
)
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONValue

__all__ = (
    "publish_automation_conversation_created",
    "publish_automation_conversation_message_events",
)

LOGGER_NAME = "SoAI.features.automation.events"
OPERATION_AUTOMATION_EVENTS_PUBLISH_CONVERSATION_CREATED = (
    "automation.events.publish_conversation_created"
)
OPERATION_AUTOMATION_EVENTS_PUBLISH_CONVERSATION_MESSAGE_EVENTS = (
    "automation.events.publish_conversation_message_events"
)


async def publish_automation_conversation_created(
    event_bus: EventBusProtocol,
    *,
    user_id: int,
    conversation_record: Mapping[str, JSONValue],
) -> None:
    created_event = build_conversation_created_event(
        user_id=user_id,
        conversation_record=conversation_record,
    )
    try:
        await event_bus.publish(created_event)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to publish automation ConversationCreatedEvent (non-critical).",
            operation=OPERATION_AUTOMATION_EVENTS_PUBLISH_CONVERSATION_CREATED,
            level="debug",
            details={"conv_id": created_event.conv_id, "user_id": user_id},
        )


async def publish_automation_conversation_message_events(
    event_bus: EventBusProtocol,
    *,
    user_id: int,
    conv_id: str,
    message_count: int,
    last_modified_at_ms: int,
) -> None:
    try:
        await publish_conversation_updated_and_message_saved(
            event_bus,
            user_id=user_id,
            conv_id=conv_id,
            message_count=message_count,
            last_modified_at_ms=last_modified_at_ms,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to publish automation conversation/message events (non-critical).",
            operation=OPERATION_AUTOMATION_EVENTS_PUBLISH_CONVERSATION_MESSAGE_EVENTS,
            level="debug",
            details={"conv_id": conv_id, "user_id": user_id},
        )
