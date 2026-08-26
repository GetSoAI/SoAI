"""SoAI - Streaming assistant placeholder persistence [backend/features/assistant_timeline/assistant_placeholder_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.assistant_timeline.message_write_versions import (
    record_assistant_timeline_message_write,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_conversations import (
        DatabaseMessagesProtocol,
    )
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("persist_streaming_assistant_placeholder",)


async def persist_streaming_assistant_placeholder(
    *,
    database_messages: DatabaseMessagesProtocol,
    runtime: AssistantTimelineRuntime,
) -> None:
    await runtime.require_mutation_allowed()
    write_result = await database_messages.append_streaming_assistant_placeholder(
        runtime.conv_id,
        runtime.user_id,
        created_at_ms=runtime.assistant_at_ms,
        assistant_turn_at_ms=runtime.assistant_turn_at_ms,
        request_id=runtime.request_id,
        model_id=runtime.model_id,
        model_variant_index=runtime.model_variant_index,
    )
    runtime.assistant_placeholder_persisted = True
    record_assistant_timeline_message_write(runtime, write_result)
