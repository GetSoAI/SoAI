"""SoAI - WebSocket conversation presence updates [backend/features/api/routes/system/events/conversation_presence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.strings import coerce_optional_trimmed_str
from features.api.routes.system.events.permissions import resolve_current_user_id

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_event_context import (
        WebsocketEventRuntimeContext,
    )

__all__ = ("handle_conversation_presence_update", "remove_conversation_presence")


def _require_presence_key(value: str | None, *, label: str) -> str:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        raise ValidationError(f"{label} is required.")
    return normalized


async def handle_conversation_presence_update(
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> None:
    device_id = _require_presence_key(
        coerce_optional_trimmed_str(data.get("device_id")),
        label="device_id",
    )
    tab_id = _require_presence_key(
        coerce_optional_trimmed_str(data.get("tab_id")),
        label="tab_id",
    )
    conversation_id = coerce_optional_trimmed_str(data.get("conversation_id"))
    previous_device_id = runtime_context.connection.conversation_presence_device_id
    previous_tab_id = runtime_context.connection.conversation_presence_tab_id
    if (
        previous_device_id is not None
        and previous_tab_id is not None
        and (previous_device_id != device_id or previous_tab_id != tab_id)
    ):
        runtime_context.api_context.dependencies.conversation_attention.remove_presence(
            user_id=resolve_current_user_id(runtime_context.connection.user),
            device_id=previous_device_id,
            tab_id=previous_tab_id,
        )
    runtime_context.connection.conversation_presence_device_id = device_id
    runtime_context.connection.conversation_presence_tab_id = tab_id
    runtime_context.api_context.dependencies.conversation_attention.update_presence(
        user_id=resolve_current_user_id(runtime_context.connection.user),
        device_id=device_id,
        tab_id=tab_id,
        conversation_id=conversation_id,
        is_visible=data.get("is_visible") is True,
        has_focus=data.get("has_focus") is True,
    )


def remove_conversation_presence(runtime_context: WebsocketEventRuntimeContext) -> None:
    device_id = runtime_context.connection.conversation_presence_device_id
    tab_id = runtime_context.connection.conversation_presence_tab_id
    if device_id is None or tab_id is None:
        return
    runtime_context.api_context.dependencies.conversation_attention.remove_presence(
        user_id=resolve_current_user_id(runtime_context.connection.user),
        device_id=device_id,
        tab_id=tab_id,
    )
