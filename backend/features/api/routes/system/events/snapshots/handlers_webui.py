"""SoAI - Snapshot handlers for WebUI resources [backend/features/api/routes/system/events/snapshots/handlers_webui.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.errors.exceptions import ValidationError
from core.notifications.notification_record_models import (
    NotificationsListRequest,
    NotificationsListResponse,
)
from core.notifications.notification_source_visibility import (
    resolve_notification_excluded_sources,
)
from core.state.access import AccessAction
from core.validation.integers import is_strict_int
from features.api.middleware.acl_enforcement import resolve_request_effective_actions
from features.api.routes.system.events.permissions import resolve_current_user_id
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "snapshot_webui_chat_activity",
    "snapshot_webui_chat_attention",
    "snapshot_webui_notifications",
    "snapshot_webui_permissions",
)


async def snapshot_webui_chat_activity(
    _data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    user_id = resolve_current_user_id(connection.user)
    conversation_ids = await connection.api_context.dependencies.chat_stream_registry.snapshot_active_conversation_ids(
        user_id=user_id,
    )
    return {"active_conversation_ids": list(conversation_ids)}


async def snapshot_webui_chat_attention(
    _data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    user_id = resolve_current_user_id(connection.user)
    conversations = await connection.api_context.dependencies.database_conversations.get_conversation_attention_snapshot(
        user_id,
    )
    return {"conversations": conversations}


async def snapshot_webui_permissions(
    _data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    granted_actions = await resolve_request_effective_actions(connection.request)
    return {
        "actions": sorted(action.value for action in granted_actions),
        "is_admin": connection.user.get("is_admin") is True,
    }


async def snapshot_webui_notifications(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    limit_value = data.get("limit")
    if limit_value is None:
        limit = 100
    elif is_strict_int(limit_value):
        limit = int(limit_value)
    else:
        raise ValidationError("webui.notifications snapshot limit must be an integer.")
    if limit <= 0 or limit > 500:
        raise ValidationError("webui.notifications snapshot limit must be between 1 and 500.")
    before_created_at_ms_value = data.get("before_created_at_ms")
    if before_created_at_ms_value is None:
        before_created_at_ms = None
    elif is_strict_int(before_created_at_ms_value):
        before_created_at_ms = int(before_created_at_ms_value)
    else:
        raise ValidationError(
            "webui.notifications snapshot before_created_at_ms must be an integer.",
        )
    before_id_value = data.get("before_id")
    if before_id_value is None:
        before_id = None
    elif isinstance(before_id_value, str) and before_id_value.strip():
        before_id = before_id_value.strip()
    else:
        raise ValidationError("webui.notifications snapshot before_id must be a string.")
    unread_only_value = data.get("unread_only")
    if unread_only_value is None:
        unread_only = False
    elif isinstance(unread_only_value, bool):
        unread_only = bool(unread_only_value)
    else:
        raise ValidationError("webui.notifications snapshot unread_only must be a boolean.")
    user_id_value = connection.user.get("id")
    if not is_strict_int(user_id_value):
        raise ValidationError("webui.notifications snapshot user id is invalid.")
    user_id = int(user_id_value)
    excluded_sources = resolve_notification_excluded_sources(
        can_read_plugins=AccessAction.PLUGIN_READ in connection.granted_actions,
    )
    list_request = NotificationsListRequest(
        limit=int(limit),
        before_created_at_ms=before_created_at_ms,
        before_id=before_id,
        unread_only=bool(unread_only),
    )
    database_notifications = connection.api_context.dependencies.database_notifications
    notifications_page = await database_notifications.list_notifications(
        user_id,
        limit=list_request.limit,
        before_created_at_ms=list_request.before_created_at_ms,
        before_id=list_request.before_id,
        unread_only=list_request.unread_only,
        excluded_sources=excluded_sources,
    )
    total_count, unread_count = await database_notifications.get_notification_counts(
        user_id,
        excluded_sources=excluded_sources,
    )
    response = NotificationsListResponse(
        notifications=notifications_page.notifications,
        total_count=int(total_count),
        unread_count=int(unread_count),
        next_cursor=notifications_page.next_cursor,
    )
    return response.model_dump(mode="json")
