"""SoAI - Shared assistant timeline tool event subscription [backend/features/assistant_timeline/tool_events_subscription.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.tool_call_event_guards import is_tool_call_stream_event
from core.events.types_base import Event
from core.events.types_system import (
    ToolCallCompletedEvent,
    ToolCallCreatedEvent,
    ToolCallOutputDeltaEvent,
    ToolCallStartedEvent,
)
from core.logging.trace import get_logger
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.publish import ensure_chat_stream_publish_lock
from features.assistant_timeline.status_preview_scheduler import (
    wake_status_preview_scheduler,
)
from features.assistant_timeline.tool_events_handler import (
    allow_post_terminal_tool_event,
    handle_tool_event_locked,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.tool_calls.protocols import DatabaseToolCallsProtocol

__all__ = ("subscribe_tool_events_for_stream",)

LOGGER_NAME = "SoAI.features.assistant_timeline.tool_events_subscription"
OPERATION = "webui_ws_chat_stream.tool_events.unsubscribe"


def subscribe_tool_events_for_stream(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
) -> tuple[asyncio.Event, Callable[[], None]]:
    done = asyncio.Event()
    logger = get_logger(LOGGER_NAME)
    unsubscribed = False

    async def handler(event: Event) -> None:
        if not is_tool_call_stream_event(event):
            return
        call_id_value = event.call_id
        call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
        tool_name_value = event.tool_name
        tool_name = tool_name_value.strip() if isinstance(tool_name_value, str) else ""
        lock = ensure_chat_stream_publish_lock(runtime)
        async with lock:
            if not allow_post_terminal_tool_event(
                runtime=runtime,
                call_id=call_id,
                tool_name=tool_name,
            ):
                return
            handling_result = await handle_tool_event_locked(
                event_bus=event_bus,
                runtime=runtime,
                database_messages=database_messages,
                database_tool_calls=database_tool_calls,
                event=event,
            )
        if handling_result.should_wake_status_preview:
            wake_status_preview_scheduler(runtime)
        if handling_result.should_unsubscribe:
            unsubscribe()

    def unsubscribe() -> None:
        nonlocal unsubscribed
        if unsubscribed:
            return
        unsubscribed = True
        for event_type in (
            ToolCallCreatedEvent,
            ToolCallStartedEvent,
            ToolCallCompletedEvent,
            ToolCallOutputDeltaEvent,
        ):
            try:
                event_bus.unsubscribe(event_type, handler)
            except RECOVERABLE_EXCEPTIONS as exception:
                coerced = coerce_to_soai_error(
                    exception,
                    operation="webui_ws_chat_stream.tool_events.unsubscribe",
                )
                log_handled_exception(
                    logger,
                    coerced,
                    message="Failed to unsubscribe tool event handler (non-critical).",
                    operation=OPERATION,
                    level="debug",
                )
                continue
        done.set()

    for event_type in (
        ToolCallCreatedEvent,
        ToolCallStartedEvent,
        ToolCallCompletedEvent,
        ToolCallOutputDeltaEvent,
    ):
        event_bus.subscribe(event_type, handler)

    return done, unsubscribe
