"""SoAI - WebUI conversation deletion side-effect events [backend/features/api/routes/webui/conversation_deletion_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.types_system import ConversationDeletedEvent
from features.api.routes.webui.conversation_attachments.events import (
    publish_knowledge_attachment_changed,
)

if TYPE_CHECKING:
    from core.conversations.conversation_deletion import DeletedConversationRecord
    from core.events.protocols import EventBusProtocol
    from features.api.runtime.context import ApiContext

__all__ = (
    "publish_conversation_deletion_side_effects",
    "publish_linked_knowledge_deletion_events",
)


async def publish_conversation_deletion_side_effects(
    api_context: ApiContext,
    *,
    user_id: int,
    deleted_records: tuple[DeletedConversationRecord, ...],
) -> None:
    for record in deleted_records:
        await api_context.dependencies.event_bus.publish(
            ConversationDeletedEvent(user_id=user_id, conv_id=record.conv_id),
        )
    await publish_linked_knowledge_deletion_events(
        api_context.dependencies.event_bus,
        deleted_records=deleted_records,
    )


async def publish_linked_knowledge_deletion_events(
    event_bus: EventBusProtocol,
    *,
    deleted_records: tuple[DeletedConversationRecord, ...],
) -> None:
    published_ids: set[str] = set()
    for deleted_record in deleted_records:
        for summary in deleted_record.linked_knowledge_summaries:
            knowledge_attachment_id = summary.get("knowledge_attachment_id")
            if not isinstance(knowledge_attachment_id, str) or not knowledge_attachment_id.strip():
                raise StateError("Deleted linked knowledge summary is missing an attachment id.")
            if knowledge_attachment_id in published_ids:
                continue
            published_ids.add(knowledge_attachment_id)
            await publish_knowledge_attachment_changed(event_bus, summary=summary)
