"""SoAI - Shared assistant timeline publish helpers that mark visible activity [backend/features/assistant_timeline/visible_activity_publishing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.assistant_timeline.processing_activity_support import (
    note_visible_activity_locked,
)
from features.assistant_timeline.publish import publish_chat_stream_event_locked

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("publish_chat_stream_event_after_visible_activity_locked",)


async def publish_chat_stream_event_after_visible_activity_locked(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_type: str,
    payload: JSONDict,
) -> None:
    note_visible_activity_locked(runtime)
    await publish_chat_stream_event_locked(
        event_bus,
        runtime,
        database_messages,
        event_type=event_type,
        payload=payload,
    )
