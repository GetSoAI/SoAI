"""SoAI - Shared assistant timeline loading-cancelled finalization [backend/features/assistant_timeline/loading_cancelled_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.assistant_timeline.loading_activity_payloads import (
    build_loading_activity_payload,
)
from features.assistant_timeline.loading_terminal_finalization import (
    publish_loading_terminal_events,
)
from features.assistant_timeline.terminal_event_publication import (
    build_cancelled_assistant_finalization,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_conversations import (
        DatabaseMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("finalize_and_publish_loading_cancelled",)


async def finalize_and_publish_loading_cancelled(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseMessagesProtocol,
    duration_ms: int,
    thinking_tail_duration_ms: int,
    reason: str,
) -> None:
    runtime.loading_activity.status = "cancelled"
    runtime.loading_activity.duration_ms = duration_ms
    normalized_reason = reason.strip() if reason.strip() else "Chat stream was cancelled."
    loading_cancelled = build_loading_activity_payload(
        runtime=runtime,
        status="cancelled",
        duration_ms=duration_ms,
        reason=normalized_reason,
        error_type="cancelled",
    )
    runtime.terminal_finalization_started = True
    await publish_loading_terminal_events(
        runtime=runtime,
        event_bus=event_bus,
        database_messages=database_messages,
        loading_activity=loading_cancelled,
        terminal_event_type="cancelled",
        terminal_payload={
            "assistant_at_ms": runtime.assistant_at_ms,
            "reason": normalized_reason,
            "code": "cancelled",
        },
        finalization=build_cancelled_assistant_finalization(
            duration_ms=duration_ms,
            thinking_tail_duration_ms=thinking_tail_duration_ms,
            reason=normalized_reason,
            code="cancelled",
        ),
    )
