"""SoAI - WebUI message write response and event outputs [backend/features/api/routes/webui/conversation_message_write_outputs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.assistant_timeline.presentation_projection import (
    project_assistant_event_timeline,
)
from core.conversations.conversation_message_sync_cursor import (
    ConversationMessageSyncCursor,
)
from core.conversations.conversation_message_window import (
    ConversationMessageCursor,
    ConversationMessageWindowResult,
    ConversationRunningActivitySnapshot,
)
from core.conversations.conversation_message_write_result import (
    ConversationMessageWriteResult,
)
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from features.api.routes.webui.conversation_attachments.events import (
    publish_unique_knowledge_attachment_summaries,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.webui_attachments.message_read_projection import (
    project_message_attachments_for_read,
)

if TYPE_CHECKING:
    from features.api.runtime.user_types import CurrentUser

__all__ = (
    "publish_message_write_knowledge_events",
    "serialize_message_sync_cursor",
    "serialize_message_window_result",
    "serialize_running_activity_snapshot",
    "serialize_assistant_stream_state",
    "serialize_message_write_result",
)


def _serialize_message_read_projection(message: JSONDict) -> JSONDict:
    serialized = dict(message)
    if serialized.get("role") != "assistant":
        return serialized
    timeline = serialized.pop("assistant_event_timeline", None)
    if not isinstance(timeline, list):
        raise ValidationError("Assistant read response requires a canonical event timeline.")
    serialized["assistant_event_timeline_projection"] = project_assistant_event_timeline(
        timeline,
    )
    return serialized


async def serialize_assistant_stream_state(
    message: JSONDict,
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
    conv_id: str,
) -> JSONDict:
    projected_messages = await project_message_attachments_for_read(
        dependencies=api_context.dependencies,
        conv_id=conv_id,
        user_id=current_user["id"],
        messages=(message,),
    )
    return _serialize_message_read_projection(projected_messages[0])


async def publish_message_write_knowledge_events(
    api_context: ApiContext,
    write_result: ConversationMessageWriteResult,
) -> None:
    await publish_unique_knowledge_attachment_summaries(
        api_context.dependencies.event_bus,
        summaries=write_result.knowledge_attachment_summaries,
    )


def serialize_message_write_result(
    write_result: ConversationMessageWriteResult,
) -> JSONDict:
    return {
        "last_modified_at_ms": write_result.last_modified_at_ms,
        "message_count": write_result.message_count,
        "messages": write_result.canonical_messages,
    }


def serialize_message_sync_cursor(sync_cursor: ConversationMessageSyncCursor) -> JSONDict:
    return {
        "timestamp": sync_cursor.latest_timestamp,
        "last_modified_at_ms": sync_cursor.last_modified_at_ms,
        "message_count": sync_cursor.message_count,
    }


def _serialize_message_cursor(cursor: ConversationMessageCursor | None) -> JSONDict | None:
    if cursor is None:
        return None
    return {
        "created_at_ms": cursor.created_at_ms,
        "id": cursor.id,
    }


async def serialize_message_window_result(
    read_result: ConversationMessageWindowResult,
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
) -> JSONDict:
    projected_messages = await project_message_attachments_for_read(
        dependencies=api_context.dependencies,
        conv_id=read_result.conv_id,
        user_id=current_user["id"],
        messages=read_result.messages,
    )
    return {
        "conv_id": read_result.conv_id,
        "messages": [_serialize_message_read_projection(message) for message in projected_messages],
        "returned_count": read_result.returned_count,
        "loaded_count_hint": read_result.loaded_count_hint,
        "total_count": read_result.total_count,
        "oldest_cursor": _serialize_message_cursor(read_result.oldest_cursor),
        "newest_cursor": _serialize_message_cursor(read_result.newest_cursor),
        "has_older": read_result.has_older,
        "has_newer": read_result.has_newer,
        "last_modified_at_ms": read_result.last_modified_at_ms,
    }


async def serialize_running_activity_snapshot(
    snapshot: ConversationRunningActivitySnapshot,
    *,
    api_context: ApiContext,
    current_user: CurrentUser,
) -> JSONDict:
    projected_messages = await project_message_attachments_for_read(
        dependencies=api_context.dependencies,
        conv_id=snapshot.conv_id,
        user_id=current_user["id"],
        messages=snapshot.running_messages,
    )
    return {
        "conv_id": snapshot.conv_id,
        "running_messages": [
            _serialize_message_read_projection(message) for message in projected_messages
        ],
        "last_modified_at_ms": snapshot.last_modified_at_ms,
    }
