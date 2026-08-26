"""SoAI - Shared conversation event publication for assistant timelines [backend/features/assistant_timeline/conversation_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.conversation_publication import (
    publish_conversation_updated_and_message_saved,
)
from features.assistant_timeline.message_write_versions import (
    require_assistant_timeline_message_write,
)
from features.assistant_timeline.models import AssistantTimelineRuntime

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol

__all__ = ("publish_chat_stream_message_events",)


async def publish_chat_stream_message_events(
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
) -> None:
    write_result = require_assistant_timeline_message_write(runtime)
    await publish_conversation_updated_and_message_saved(
        event_bus,
        user_id=runtime.user_id,
        conv_id=runtime.conv_id,
        message_count=write_result.message_count,
        last_modified_at_ms=write_result.last_modified_at_ms,
    )
