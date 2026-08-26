"""SoAI - Snapshot handlers for WebUI chat tool calls [backend/features/api/routes/system/events/snapshots/handlers_chat_tool_calls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.errors.exceptions import ValidationError
from core.tool_calls.live_event_paging import resolve_tool_call_live_event_page_limit
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import (
    coerce_optional_non_negative_int_strict,
    coerce_optional_positive_int_strict,
)
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "snapshot_webui_chat_tool_call_live_events_page",
    "snapshot_webui_chat_tool_calls_by_call_id",
)


async def snapshot_webui_chat_tool_calls_by_call_id(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    conv_id_value = data.get("conv_id")
    conv_id = conv_id_value.strip() if isinstance(conv_id_value, str) else ""
    if not conv_id:
        raise ValidationError("webui.chat.tool_calls.by_call_id snapshot requires conv_id")

    call_id_value = data.get("call_id")
    call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
    if not call_id:
        raise ValidationError("webui.chat.tool_calls.by_call_id snapshot requires call_id")
    assistant_turn_at_ms = coerce_optional_positive_int_strict(data.get("assistant_turn_at_ms"))
    if assistant_turn_at_ms is None:
        raise ValidationError(
            "webui.chat.tool_calls.by_call_id snapshot requires assistant_turn_at_ms",
        )
    model_variant_index = coerce_optional_non_negative_int_strict(data.get("model_variant_index"))
    if model_variant_index is None:
        raise ValidationError(
            "webui.chat.tool_calls.by_call_id snapshot requires model_variant_index",
        )

    user_id_value = connection.user.get("id")
    user_id: int = user_id_value if is_strict_int(user_id_value) else 0
    conversation = (
        await connection.api_context.dependencies.database_conversations.get_conversation(
            conv_id,
            user_id,
        )
    )
    if conversation is None:
        raise ValidationError("Conversation not found.")

    database_tool_calls = connection.api_context.dependencies.database_tool_calls
    tool_call = await database_tool_calls.get_tool_call_for_assistant_variant(
        conv_id=conv_id,
        call_id=call_id,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
    )
    if tool_call is None:
        raise ValidationError("Tool call not found.")
    return tool_call


async def snapshot_webui_chat_tool_call_live_events_page(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    conv_id_value = data.get("conv_id")
    conv_id = conv_id_value.strip() if isinstance(conv_id_value, str) else ""
    if not conv_id:
        raise ValidationError("webui.chat.tool_call_live_events.page snapshot requires conv_id")
    call_id_value = data.get("call_id")
    call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
    if not call_id:
        raise ValidationError("webui.chat.tool_call_live_events.page snapshot requires call_id")
    assistant_turn_at_ms = coerce_optional_positive_int_strict(data.get("assistant_turn_at_ms"))
    if assistant_turn_at_ms is None:
        raise ValidationError(
            "webui.chat.tool_call_live_events.page snapshot requires assistant_turn_at_ms",
        )
    model_variant_index = coerce_optional_non_negative_int_strict(data.get("model_variant_index"))
    if model_variant_index is None:
        raise ValidationError(
            "webui.chat.tool_call_live_events.page snapshot requires model_variant_index",
        )
    before_live_sequence = coerce_optional_non_negative_int_strict(data.get("before_live_sequence"))
    limit = coerce_optional_positive_int_strict(data.get("limit"))
    page_limit = resolve_tool_call_live_event_page_limit(limit)
    user_id_value = connection.user.get("id")
    user_id: int = user_id_value if is_strict_int(user_id_value) else 0
    database_tool_calls = connection.api_context.dependencies.database_tool_calls
    page = await database_tool_calls.get_tool_call_live_events_page(
        conv_id=conv_id,
        user_id=user_id,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
        call_id=call_id,
        before_live_sequence=before_live_sequence,
        limit=page_limit,
    )
    if page is None:
        raise ValidationError("Conversation not found.")
    return page
