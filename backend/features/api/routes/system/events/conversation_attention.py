"""SoAI - WebSocket conversation attention mutations [backend/features/api/routes/system/events/conversation_attention.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import SecurityError, ValidationError
from core.state.access import AccessAction
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str
from features.api.routes.system.events.permissions import resolve_current_user_id

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_event_context import (
        WebsocketEventRuntimeContext,
    )

__all__ = ("handle_conversation_attention_mark_seen",)


async def handle_conversation_attention_mark_seen(
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> None:
    if AccessAction.AUTH_COOKIE not in runtime_context.connection.granted_actions:
        raise SecurityError("Conversation attention requires authentication.")
    if "conversation_id" in data:
        if "seen_through_attention_id" in data:
            raise ValidationError("Conversation attention mutation must select one target.")
        conversation_id = coerce_optional_trimmed_str(data.get("conversation_id"))
        if conversation_id is None:
            raise ValidationError("conversation_id must be a non-empty string.")
        assistant_at_ms = data.get("assistant_at_ms")
        if not is_strict_int(assistant_at_ms) or assistant_at_ms <= 0:
            raise ValidationError("assistant_at_ms must be a positive integer.")
        await runtime_context.api_context.dependencies.database_conversations.mark_conversation_attention_seen(
            resolve_current_user_id(runtime_context.connection.user),
            conversation_id,
            int(assistant_at_ms),
        )
        return
    watermark_value = data.get("seen_through_attention_id")
    if not is_strict_int(watermark_value) or watermark_value <= 0:
        raise ValidationError("seen_through_attention_id must be a positive integer.")
    await runtime_context.api_context.dependencies.database_conversations.mark_conversation_attention_seen_through(
        resolve_current_user_id(runtime_context.connection.user),
        int(watermark_value),
    )
