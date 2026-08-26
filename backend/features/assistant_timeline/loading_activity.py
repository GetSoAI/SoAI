"""SoAI - Shared assistant timeline loading activity state [backend/features/assistant_timeline/loading_activity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.protocols_database_message_streaming import (
    DatabaseStreamingMessagesProtocol,
)
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.activity_status_sets import (
    TIMELINE_ACTIVITY_STATUS_COMPLETED,
    TIMELINE_ACTIVITY_STATUS_RUNNING,
)
from features.assistant_timeline.activity_timing import (
    resolve_activity_running_duration_ms,
)
from features.assistant_timeline.loading_activity_payloads import (
    build_loading_activity_event_payload,
    build_loading_activity_payload,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.publish import (
    ensure_chat_stream_publish_lock,
    publish_chat_stream_event_locked,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol

__all__ = ("mark_loading_completed_if_running",)


async def mark_loading_completed_if_running(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseStreamingMessagesProtocol,
) -> bool:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        if runtime.loading_activity.status != TIMELINE_ACTIVITY_STATUS_RUNNING:
            return False
        duration_ms = resolve_activity_running_duration_ms(
            runtime.loading_activity,
            now_monotonic_ms=int(monotonic_ms()),
        )
        runtime.loading_activity.status = TIMELINE_ACTIVITY_STATUS_COMPLETED
        runtime.loading_activity.duration_ms = duration_ms
        loading_completed = build_loading_activity_payload(
            runtime=runtime,
            status=TIMELINE_ACTIVITY_STATUS_COMPLETED,
            duration_ms=duration_ms,
            reason=None,
            error_type=None,
        )
        await publish_chat_stream_event_locked(
            event_bus,
            runtime,
            database_messages,
            event_type="loading_activity",
            payload=build_loading_activity_event_payload(
                runtime=runtime,
                loading_activity=loading_completed,
            ),
        )
    return True
