"""SoAI - Conversation clone write operations [backend/database/repositories/users/conversation_clone_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.timing.epoch import epoch_ms
from database.core.flags import FEATURE_PROMPTS
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.conversation_clone_message_history import (
    copy_cloned_message_history,
)
from database.repositories.users.conversation_quiescence import (
    clear_conversation_selection,
    prepare_conversation_selection,
    require_selected_conversations_quiescent,
)
from database.repositories.users.conversation_sync_operations import (
    sync_get_conversation,
)
from database.repositories.users.internal_protocols import DatabaseCoreOwnerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("clone_conversation_method", "sync_clone_conversation")


def _is_source_conversation_owned(
    conn: sqlite3.Connection,
    source_conv_id: str,
    user_id: int,
) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM webui_conversations WHERE id = ? AND user_id = ? LIMIT 1",
            (source_conv_id, user_id),
        ).fetchone()
        is not None
    )


def _insert_cloned_conversation(
    conn: sqlite3.Connection,
    *,
    source_conv_id: str,
    user_id: int,
    target_conv_id: str,
    now: int,
) -> bool:
    try:
        return (
            conn.execute(
                """
                INSERT INTO webui_conversations (
                    id, user_id, title, created_at_ms, last_modified_at_ms, model_settings,
                    color, is_favorite, is_automation, is_archived
                )
                SELECT ?, c.user_id, c.title, ?, ?,
                    CASE
                        WHEN c.is_messaging = 1
                            THEN COALESCE(messaging_account.model_settings_json, c.model_settings)
                        ELSE c.model_settings
                    END,
                    c.color, c.is_favorite, c.is_automation, 0
                FROM webui_conversations AS c
                LEFT JOIN messaging_thread_bindings AS messaging_binding
                  ON messaging_binding.conv_id = c.id
                 AND messaging_binding.user_id = c.user_id
                LEFT JOIN messaging_accounts AS messaging_account
                  ON messaging_account.account_id = messaging_binding.account_id
                 AND messaging_account.user_id = c.user_id
                WHERE c.id = ? AND c.user_id = ?
                """,
                (target_conv_id, now, now, source_conv_id, user_id),
            ).rowcount
            > 0
        )
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        if constraint_type in ("unique", "primary_key"):
            raise ConflictError(
                f"Conversation with ID '{target_conv_id}' already exists."
            ) from exception
        if constraint_type == "foreign_key":
            raise ValidationError(f"User with ID '{user_id}' does not exist.") from exception
        if constraint_type == "check":
            raise ValidationError(
                f"Invalid cloned conversation data: constraint violation on {detail or 'unknown field'}.",
            ) from exception
        raise StateError(f"Database constraint violation: {exception}") from exception


def _copy_assistant_events(
    conn: sqlite3.Connection, source_conv_id: str, target_conv_id: str
) -> None:
    conn.execute(
        """
        INSERT INTO webui_assistant_message_events (
            conv_id, assistant_at_ms, sequence, assistant_revision, event_type,
            payload_json, created_at_ms
        )
        SELECT ?, assistant_at_ms, sequence, assistant_revision, event_type, payload_json, created_at_ms
        FROM webui_assistant_message_events
        WHERE conv_id = ?
        ORDER BY assistant_at_ms ASC, sequence ASC
        """,
        (target_conv_id, source_conv_id),
    )


def _copy_tool_calls(conn: sqlite3.Connection, source_conv_id: str, target_conv_id: str) -> None:
    conn.execute(
        """
        INSERT INTO webui_chat_tool_calls (
            id, call_id, conv_id, turn_id, iteration_index, message_index, assistant_at_ms,
            assistant_turn_at_ms, model_variant_index, tool_name, tool_arguments, tool_result,
            owner_task_id, status, error_message, duration_ms, started_at_ms, live_revision,
            last_live_event_at_ms, last_live_sequence, sequence_index, content_index_before,
            thinking_index_before, thinking_duration_before_ms, collapsed, created_at_ms,
            completed_at_ms
        )
        SELECT
            ? || ':' || id, call_id, ?, turn_id, iteration_index, message_index, assistant_at_ms,
            assistant_turn_at_ms, model_variant_index, tool_name, tool_arguments, tool_result,
            NULL, status, error_message, duration_ms, started_at_ms, live_revision,
            last_live_event_at_ms, last_live_sequence, sequence_index, content_index_before,
            thinking_index_before, thinking_duration_before_ms, collapsed, created_at_ms,
            completed_at_ms
        FROM webui_chat_tool_calls
        WHERE conv_id = ?
        ORDER BY assistant_turn_at_ms ASC, model_variant_index ASC, sequence_index ASC
        """,
        (target_conv_id, target_conv_id, source_conv_id),
    )


def _restore_assistant_finalization(
    conn: sqlite3.Connection,
    source_conv_id: str,
    target_conv_id: str,
) -> None:
    conn.execute(
        """
        UPDATE webui_messages AS target
           SET finalized_at_ms = (
               SELECT source.finalized_at_ms
               FROM webui_messages AS source
               WHERE source.conv_id = ?
                 AND source.role = 'assistant'
                 AND source.created_at_ms = target.created_at_ms
                 AND source.model_variant_index = target.model_variant_index
               LIMIT 1
           )
         WHERE target.conv_id = ? AND target.role = 'assistant'
        """,
        (source_conv_id, target_conv_id),
    )


def sync_clone_conversation(
    conn: sqlite3.Connection,
    source_conv_id: str,
    user_id: int,
    target_conv_id: str | None = None,
) -> JSONDict | None:
    resolved_target_conv_id = target_conv_id or f"conv_{uuid.uuid4().hex}"
    if not _is_source_conversation_owned(conn, source_conv_id, user_id):
        return None
    prepare_conversation_selection(conn, (source_conv_id,))
    try:
        require_selected_conversations_quiescent(conn, user_id=user_id)
    finally:
        clear_conversation_selection(conn)
    if not _insert_cloned_conversation(
        conn,
        source_conv_id=source_conv_id,
        user_id=user_id,
        target_conv_id=resolved_target_conv_id,
        now=epoch_ms(),
    ):
        return None
    copy_cloned_message_history(
        conn,
        source_conv_id=source_conv_id,
        target_conv_id=resolved_target_conv_id,
        user_id=user_id,
    )
    _copy_assistant_events(conn, source_conv_id, resolved_target_conv_id)
    _copy_tool_calls(conn, source_conv_id, resolved_target_conv_id)
    _restore_assistant_finalization(conn, source_conv_id, resolved_target_conv_id)
    return sync_get_conversation(conn, resolved_target_conv_id, user_id)


async def clone_conversation_method(
    self: DatabaseCoreOwnerProtocol,
    source_conv_id: str,
    user_id: int,
    *,
    target_conv_id: str | None = None,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
    return await self.core.writer.queue_write_operation(
        sync_clone_conversation,
        source_conv_id,
        user_id,
        target_conv_id,
    )
