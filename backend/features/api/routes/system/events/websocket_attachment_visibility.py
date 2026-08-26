"""SoAI - WebSocket attachment event conversation visibility [backend/features/api/routes/system/events/websocket_attachment_visibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.types_base import Event
from core.events.types_system import (
    ConversationAttachmentChangedEvent,
    KnowledgeAttachmentChangedEvent,
)
from features.api.routes.system.events.permissions import resolve_current_user_id

if TYPE_CHECKING:
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("attachment_event_visible_to_connection",)


async def attachment_event_visible_to_connection(
    event: Event,
    *,
    connection: WebsocketConnection,
) -> bool:
    if not isinstance(
        event,
        ConversationAttachmentChangedEvent | KnowledgeAttachmentChangedEvent,
    ):
        return True
    user_id = resolve_current_user_id(connection.user)
    if event.user_id != user_id:
        return False
    conv_id = event.conv_id.strip()
    if not conv_id:
        return False
    conversation = (
        await connection.api_context.dependencies.database_conversations.get_conversation(
            conv_id,
            user_id,
        )
    )
    return conversation is not None
