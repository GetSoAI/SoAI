"""SoAI - WebSocket selected chat presentation interest validation [backend/features/api/routes/system/events/websocket_chat_presentation_interest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONValue
from core.users.user_id import coerce_optional_user_id
from features.api.routes.system.events.websocket_event_context import (
    WebsocketEventRuntimeContext,
)

__all__ = (
    "chat_presentation_conversation_is_visible",
    "normalize_chat_presentation_selector",
)


def normalize_chat_presentation_selector(
    value: JSONValue | None,
    *,
    presentation_requested: bool,
    selector_present: bool,
) -> tuple[bool, str | None]:
    if not selector_present:
        return (False, None)
    if not presentation_requested:
        return (value is None, None)
    if not isinstance(value, str):
        return (False, None)
    normalized = value.strip()
    if not normalized or normalized != value:
        return (False, None)
    return (True, normalized)


async def chat_presentation_conversation_is_visible(
    conversation_id: str,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> bool:
    user_id = coerce_optional_user_id(runtime_context.connection.user.get("id"))
    if user_id is None:
        return False
    conversation = (
        await runtime_context.api_context.dependencies.database_conversations.get_conversation(
            conversation_id,
            user_id,
        )
    )
    return conversation is not None
