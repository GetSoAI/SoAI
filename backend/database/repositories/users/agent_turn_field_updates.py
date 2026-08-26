"""SoAI - Agent turn field update transactions [backend/database/repositories/users/agent_turn_field_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable
from database.repositories.users.agent_turn_rows import format_agent_turn_row
from database.repositories.users.agent_turn_transactions import load_turn_row

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_write_turn_assistant_text",
    "sync_write_turn_token_usage",
)


def sync_write_turn_token_usage(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    turn_id: str,
    execution_token: str,
    token_usage: JSONDict,
    updated_at_ms: int | None = None,
) -> JSONDict | None:
    normalized_execution_token = execution_token.strip()
    if not normalized_execution_token:
        raise ValidationError("Agent turn execution token is required.")
    token_usage_json = serialize_json_compact_stable(token_usage)
    normalized_updated_at_ms = (
        int(updated_at_ms) if updated_at_ms is not None and updated_at_ms >= 0 else None
    )
    cursor = sqlite_conn.execute(
        """
        UPDATE webui_agent_turns
           SET token_usage_json = ?,
               updated_at_ms = COALESCE(?, updated_at_ms)
         WHERE conv_id = ?
           AND user_id = ?
           AND turn_id = ?
           AND execution_token = ?
        """,
        (
            token_usage_json,
            normalized_updated_at_ms,
            conv_id,
            int(user_id),
            turn_id,
            normalized_execution_token,
        ),
    )
    if int(cursor.rowcount) <= 0:
        return None
    persisted_row = load_turn_row(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
    )
    return format_agent_turn_row(persisted_row)


def sync_write_turn_assistant_text(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    turn_id: str,
    execution_token: str,
    assistant_text: str,
    updated_at_ms: int | None = None,
) -> JSONDict | None:
    normalized_execution_token = execution_token.strip()
    if not normalized_execution_token:
        raise ValidationError("Agent turn execution token is required.")
    normalized_updated_at_ms = (
        int(updated_at_ms) if updated_at_ms is not None and updated_at_ms >= 0 else None
    )
    cursor = sqlite_conn.execute(
        """
        UPDATE webui_agent_turns
           SET assistant_text = ?,
               updated_at_ms = COALESCE(?, updated_at_ms)
         WHERE conv_id = ?
           AND user_id = ?
           AND turn_id = ?
           AND execution_token = ?
        """,
        (
            assistant_text,
            normalized_updated_at_ms,
            conv_id,
            int(user_id),
            turn_id,
            normalized_execution_token,
        ),
    )
    if int(cursor.rowcount) <= 0:
        return None
    persisted_row = load_turn_row(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
    )
    return format_agent_turn_row(persisted_row)
