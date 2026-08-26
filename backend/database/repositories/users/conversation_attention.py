"""SoAI - Durable conversation terminal attention operations [backend/database/repositories/users/conversation_attention.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError, ValidationError
from core.events.domain_event_payload import build_domain_event_payload
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from database.core.flags import FEATURE_PROMPTS
from database.core.query_execution import query_to_dicts, sync_fetch_all_as_json_dicts
from database.core.row_materialization import sqlite_row_dicts_to_json_dicts
from database.repositories.event_outbox.sync_ops import sync_enqueue_domain_event_payload
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)

if TYPE_CHECKING:
    from database.repositories.users.internal_protocols import DatabaseDomainEventOwnerProtocol

__all__ = (
    "get_conversation_attention_snapshot_method",
    "mark_conversation_attention_seen_method",
    "mark_conversation_attention_seen_through_method",
    "read_conversation_attention",
    "sync_list_conversation_attention",
    "sync_mark_conversation_attention_seen",
    "sync_mark_conversation_attention_seen_through",
    "sync_replace_conversation_attention",
)

EVENT_TYPE = "ConversationAttentionChangedEvent"
ATTENTION_SNAPSHOT_SQL = """
    SELECT
        attention.id AS attention_id,
        message.conv_id AS conversation_id,
        message.created_at_ms AS assistant_at_ms,
        CASE WHEN message.finish_reason = 'error' THEN 'error' ELSE 'complete' END
            AS terminal_status
    FROM webui_conversation_attention AS attention
    JOIN webui_messages AS message ON message.id = attention.assistant_message_id
    JOIN webui_conversations AS conversation ON conversation.id = message.conv_id
    WHERE conversation.user_id = ?
    ORDER BY attention.id
"""


async def get_conversation_attention_snapshot_method(
    self: DatabaseDomainEventOwnerProtocol,
    user_id: int,
) -> list[JSONDict]:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
    return await self.core.reader.execute_read(
        read_conversation_attention,
        user_id=user_id,
    )


async def mark_conversation_attention_seen_method(
    self: DatabaseDomainEventOwnerProtocol,
    user_id: int,
    conv_id: str,
    assistant_at_ms: int,
) -> bool:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
    changed = await self.core.writer.queue_write_operation(
        sync_mark_conversation_attention_seen,
        user_id,
        conv_id,
        assistant_at_ms,
        epoch_ms(),
    )
    if changed:
        notify_domain_event_outbox_dispatch_requested(self.event_bus)
    return changed


async def mark_conversation_attention_seen_through_method(
    self: DatabaseDomainEventOwnerProtocol,
    user_id: int,
    seen_through_attention_id: int,
) -> bool:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
    changed = await self.core.writer.queue_write_operation(
        sync_mark_conversation_attention_seen_through,
        user_id,
        seen_through_attention_id,
        epoch_ms(),
    )
    if changed:
        notify_domain_event_outbox_dispatch_requested(self.event_bus)
    return changed


def _enqueue_attention_changed_event(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    conv_id: str | None,
    created_at_ms: int,
) -> None:
    payload = build_domain_event_payload(
        timestamp_unix=created_at_ms / 1000.0,
        fields={"user_id": user_id, "conv_id": conv_id},
    )
    sync_enqueue_domain_event_payload(
        conn,
        event_type=EVENT_TYPE,
        payload=payload,
        created_at_ms=created_at_ms,
    )


def _require_owned_assistant_message(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    conv_id: str,
    assistant_message_id: int,
) -> None:
    row = conn.execute(
        """
        SELECT 1
        FROM webui_messages AS message
        JOIN webui_conversations AS conversation ON conversation.id = message.conv_id
        WHERE message.id = ? AND message.conv_id = ? AND message.role = 'assistant'
            AND conversation.user_id = ?
        """,
        (assistant_message_id, conv_id, user_id),
    ).fetchone()
    if row is None:
        raise StateError("Conversation attention assistant message is unavailable.")


def sync_replace_conversation_attention(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    conv_id: str,
    assistant_message_id: int,
    finish_reason: str | None,
    created_at_ms: int,
) -> None:
    _require_owned_assistant_message(
        conn,
        user_id=user_id,
        conv_id=conv_id,
        assistant_message_id=assistant_message_id,
    )
    conn.execute(
        """
        DELETE FROM webui_conversation_attention
        WHERE assistant_message_id IN (
            SELECT id FROM webui_messages WHERE conv_id = ? AND role = 'assistant'
        )
        """,
        (conv_id,),
    )
    if finish_reason != "cancelled":
        conn.execute(
            "INSERT INTO webui_conversation_attention (assistant_message_id) VALUES (?)",
            (assistant_message_id,),
        )
    _enqueue_attention_changed_event(
        conn,
        user_id=user_id,
        conv_id=conv_id,
        created_at_ms=created_at_ms,
    )


def sync_list_conversation_attention(
    conn: sqlite3.Connection,
    *,
    user_id: int,
) -> list[JSONDict]:
    cursor = conn.execute(ATTENTION_SNAPSHOT_SQL, (user_id,))
    return sync_fetch_all_as_json_dicts(cursor)


async def read_conversation_attention(
    database: aiosqlite.Connection,
    *,
    user_id: int,
) -> list[JSONDict]:
    rows = await query_to_dicts(database, ATTENTION_SNAPSHOT_SQL, (user_id,))
    return sqlite_row_dicts_to_json_dicts(rows)


def sync_mark_conversation_attention_seen(
    conn: sqlite3.Connection,
    user_id: int,
    conv_id: str,
    assistant_at_ms: int,
    created_at_ms: int,
) -> bool:
    changed = _delete_conversation_attention(
        conn,
        user_id=user_id,
        conv_id=conv_id,
        assistant_at_ms=assistant_at_ms,
    )
    if not changed:
        return False
    _enqueue_attention_changed_event(
        conn,
        user_id=user_id,
        conv_id=conv_id,
        created_at_ms=created_at_ms,
    )
    return True


def _delete_conversation_attention(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    conv_id: str,
    assistant_at_ms: int,
) -> bool:
    cursor = conn.execute(
        """
        DELETE FROM webui_conversation_attention
        WHERE assistant_message_id IN (
            SELECT message.id
            FROM webui_messages AS message
            JOIN webui_conversations AS conversation ON conversation.id = message.conv_id
            WHERE message.conv_id = ? AND message.created_at_ms = ?
                AND conversation.user_id = ?
        )
        """,
        (conv_id, assistant_at_ms, user_id),
    )
    return cursor.rowcount > 0


def sync_mark_conversation_attention_seen_through(
    conn: sqlite3.Connection,
    user_id: int,
    seen_through_attention_id: int,
    created_at_ms: int,
) -> bool:
    if seen_through_attention_id <= 0:
        raise ValidationError("Conversation attention watermark must be positive.")
    cursor = conn.execute(
        """
        DELETE FROM webui_conversation_attention
        WHERE id <= ? AND assistant_message_id IN (
            SELECT message.id
            FROM webui_messages AS message
            JOIN webui_conversations AS conversation ON conversation.id = message.conv_id
            WHERE conversation.user_id = ?
        )
        """,
        (seen_through_attention_id, user_id),
    )
    if cursor.rowcount <= 0:
        return False
    _enqueue_attention_changed_event(
        conn,
        user_id=user_id,
        conv_id=None,
        created_at_ms=created_at_ms,
    )
    return True
