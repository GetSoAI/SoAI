"""SoAI - Cursor-window conversation message reads [backend/database/repositories/users/message_window_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.conversations.conversation_message_window import (
    ConversationMessageCursor,
    ConversationMessageWindowResult,
)
from core.errors.exceptions import ValidationError
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import is_strict_int
from core.validation.requirements import require_non_negative_int
from database.core.query_execution import query_one_to_dict
from database.core.sqlite_values import SQLiteValue
from database.repositories.users.message_row_mapping import (
    build_message_payload_from_row,
)
from database.repositories.users.message_window_assistant_details import (
    attach_window_assistant_details,
)
from database.repositories.users.message_window_row_selection import (
    load_window_message_rows,
)
from database.repositories.users.read_transactions import run_user_read_transaction

if TYPE_CHECKING:
    from core.conversations.conversation_message_window import (
        ConversationMessageWindowDirection,
    )

__all__ = ("load_conversation_message_window",)


def _cursor_from_message(message: dict[str, SQLiteValue]) -> ConversationMessageCursor:
    created_at_ms = require_unix_epoch_ms(
        message.get("created_at_ms"),
        error_message="Conversation message created_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    message_id = require_non_negative_int(
        message.get("id"),
        error_message="Conversation message id must be a non-negative integer.",
    )
    return ConversationMessageCursor(created_at_ms=created_at_ms, id=message_id)


async def _has_row_before(
    database: aiosqlite.Connection,
    user_id: int,
    conv_id: str,
    cursor: ConversationMessageCursor,
) -> bool:
    row = await query_one_to_dict(
        database,
        """
        SELECT 1
        FROM webui_messages AS m
        INNER JOIN webui_conversations AS c ON c.id = m.conv_id
        WHERE c.user_id = ?
          AND m.conv_id = ?
          AND (m.created_at_ms < ? OR (m.created_at_ms = ? AND m.id < ?))
        LIMIT 1
        """,
        (user_id, conv_id, cursor.created_at_ms, cursor.created_at_ms, cursor.id),
    )
    return row is not None


async def _has_row_after(
    database: aiosqlite.Connection,
    user_id: int,
    conv_id: str,
    cursor: ConversationMessageCursor,
) -> bool:
    row = await query_one_to_dict(
        database,
        """
        SELECT 1
        FROM webui_messages AS m
        INNER JOIN webui_conversations AS c ON c.id = m.conv_id
        WHERE c.user_id = ?
          AND m.conv_id = ?
          AND (m.created_at_ms > ? OR (m.created_at_ms = ? AND m.id > ?))
        LIMIT 1
        """,
        (user_id, conv_id, cursor.created_at_ms, cursor.created_at_ms, cursor.id),
    )
    return row is not None


async def _load_conversation_message_window_transaction(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
    direction: ConversationMessageWindowDirection,
    limit: int,
    cursor_created_at_ms: int | None,
    cursor_id: int | None,
    anchor_created_at_ms: int | None,
    anchor_id: int | None,
) -> ConversationMessageWindowResult | None:
    conversation_row = await query_one_to_dict(
        database,
        "SELECT last_modified_at_ms, message_count FROM webui_conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    if conversation_row is None:
        return None
    last_modified_at_ms = require_unix_epoch_ms(
        conversation_row.get("last_modified_at_ms"),
        error_message="Conversation last_modified_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    total_count_value = conversation_row.get("message_count")
    if not is_strict_int(total_count_value) or total_count_value < 0:
        raise ValidationError("Conversation message_count must be a non-negative integer.")
    expanded_rows = await load_window_message_rows(
        database,
        conv_id=conv_id,
        direction=direction,
        limit=limit,
        cursor_created_at_ms=cursor_created_at_ms,
        cursor_id=cursor_id,
        anchor_created_at_ms=anchor_created_at_ms,
        anchor_id=anchor_id,
    )
    messages = [build_message_payload_from_row(row) for row in expanded_rows]
    await attach_window_assistant_details(database, conv_id=conv_id, messages=messages)
    oldest_cursor = _cursor_from_message(expanded_rows[0]) if expanded_rows else None
    newest_cursor = _cursor_from_message(expanded_rows[-1]) if expanded_rows else None
    has_older = (
        False
        if oldest_cursor is None
        else await _has_row_before(database, user_id, conv_id, oldest_cursor)
    )
    has_newer = (
        False
        if newest_cursor is None
        else await _has_row_after(database, user_id, conv_id, newest_cursor)
    )
    return ConversationMessageWindowResult(
        conv_id=conv_id,
        messages=messages,
        returned_count=len(messages),
        loaded_count_hint=len(messages),
        total_count=int(total_count_value),
        oldest_cursor=oldest_cursor,
        newest_cursor=newest_cursor,
        has_older=has_older,
        has_newer=has_newer,
        last_modified_at_ms=last_modified_at_ms,
    )


async def load_conversation_message_window(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
    direction: ConversationMessageWindowDirection,
    limit: int,
    cursor_created_at_ms: int | None,
    cursor_id: int | None,
    anchor_created_at_ms: int | None,
    anchor_id: int | None,
) -> ConversationMessageWindowResult | None:
    async def _transaction(
        transaction_database: aiosqlite.Connection,
    ) -> ConversationMessageWindowResult | None:
        return await _load_conversation_message_window_transaction(
            transaction_database,
            conv_id=conv_id,
            user_id=user_id,
            direction=direction,
            limit=limit,
            cursor_created_at_ms=cursor_created_at_ms,
            cursor_id=cursor_id,
            anchor_created_at_ms=anchor_created_at_ms,
            anchor_id=anchor_id,
        )

    return await run_user_read_transaction(database, _transaction)
