"""SoAI - Conversation synchronous database write operations [backend/database/repositories/users/conversation_sync_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.prompts.colors import validate_prompt_color
from core.timing.epoch import epoch_ms
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_query_projection import (
    conversation_query_joins_sql,
    conversation_query_select_sql,
)
from database.repositories.users.conversation_row_formatter import (
    format_conversation_row,
)
from database.repositories.users.conversation_versioning import NEXT_LAST_MODIFIED_SQL

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_get_conversation",
    "sync_update_conversation_color",
    "sync_update_conversation_favorite",
    "sync_update_conversation_title",
    "sync_update_conversation_title_if_matches",
)


def sync_get_conversation(conn: sqlite3.Connection, conv_id: str, user_id: int) -> JSONDict | None:
    cursor = conn.execute(
        f"""
        SELECT c.*, {conversation_query_select_sql()}
        FROM webui_conversations AS c
        {conversation_query_joins_sql()}
        WHERE c.id = ? AND c.user_id = ?
        """,
        (conv_id, user_id),
    )
    return format_conversation_row(sync_fetch_one_as_dict(cursor))


def sync_update_conversation_title(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    new_title: str,
) -> JSONDict | None:
    existing_cursor = conn.execute(
        "SELECT title FROM webui_conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    existing_row = existing_cursor.fetchone()
    if not existing_row:
        return None
    current_title = existing_row[0]
    if isinstance(current_title, str) and current_title == new_title:
        return sync_get_conversation(conn, conv_id, user_id)
    update_time = epoch_ms()
    if (
        conn.execute(
            f"UPDATE webui_conversations SET title = ?, last_modified_at_ms = {NEXT_LAST_MODIFIED_SQL} WHERE id = ? AND user_id = ?",
            (new_title, update_time, update_time, conv_id, user_id),
        ).rowcount
        > 0
    ):
        return sync_get_conversation(conn, conv_id, user_id)
    return None


def sync_update_conversation_title_if_matches(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    expected_title: str,
    new_title: str,
) -> JSONDict | None:
    existing_cursor = conn.execute(
        "SELECT title FROM webui_conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    existing_row = existing_cursor.fetchone()
    if not existing_row:
        return None
    current_title = existing_row[0]
    if not isinstance(current_title, str) or current_title != expected_title:
        return None
    if current_title == new_title:
        return sync_get_conversation(conn, conv_id, user_id)
    update_time = epoch_ms()
    if (
        conn.execute(
            f"UPDATE webui_conversations SET title = ?, last_modified_at_ms = {NEXT_LAST_MODIFIED_SQL} WHERE id = ? AND user_id = ? AND title = ?",
            (new_title, update_time, update_time, conv_id, user_id, expected_title),
        ).rowcount
        > 0
    ):
        return sync_get_conversation(conn, conv_id, user_id)
    return None


def sync_update_conversation_color(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    color: str | None,
) -> JSONDict | None:
    sanitized = validate_prompt_color(color)
    existing_cursor = conn.execute(
        "SELECT color FROM webui_conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    existing_row = existing_cursor.fetchone()
    if not existing_row:
        return None
    current_color = existing_row[0]
    if current_color is None and sanitized is None:
        return sync_get_conversation(conn, conv_id, user_id)
    if isinstance(current_color, str) and isinstance(sanitized, str) and current_color == sanitized:
        return sync_get_conversation(conn, conv_id, user_id)
    update_time = epoch_ms()
    if (
        conn.execute(
            f"UPDATE webui_conversations SET color = ?, last_modified_at_ms = {NEXT_LAST_MODIFIED_SQL} WHERE id = ? AND user_id = ?",
            (sanitized, update_time, update_time, conv_id, user_id),
        ).rowcount
        > 0
    ):
        return sync_get_conversation(conn, conv_id, user_id)
    return None


def sync_update_conversation_favorite(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    is_favorite: bool,
) -> JSONDict | None:
    existing_cursor = conn.execute(
        "SELECT is_favorite FROM webui_conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    existing_row = existing_cursor.fetchone()
    if not existing_row:
        return None
    current_value = existing_row[0]
    if isinstance(current_value, bool):
        current_favorite = current_value
    elif isinstance(current_value, int):
        if current_value not in (0, 1):
            raise StateError("Conversation is_favorite is invalid.")
        current_favorite = current_value == 1
    elif isinstance(current_value, str | float):
        try:
            favorite_int = int(current_value)
        except (TypeError, ValueError) as exception:
            raise StateError("Conversation is_favorite is invalid.") from exception
        if favorite_int not in (0, 1):
            raise StateError("Conversation is_favorite is invalid.")
        current_favorite = favorite_int == 1
    else:
        raise StateError("Conversation is_favorite is invalid.")
    if current_favorite == is_favorite:
        return sync_get_conversation(conn, conv_id, user_id)
    update_time = epoch_ms()
    if (
        conn.execute(
            f"UPDATE webui_conversations SET is_favorite = ?, last_modified_at_ms = {NEXT_LAST_MODIFIED_SQL} WHERE id = ? AND user_id = ?",
            (1 if is_favorite else 0, update_time, update_time, conv_id, user_id),
        ).rowcount
        > 0
    ):
        return sync_get_conversation(conn, conv_id, user_id)
    return None
