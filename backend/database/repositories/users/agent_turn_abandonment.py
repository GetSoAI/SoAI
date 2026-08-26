"""SoAI - Agent turn atomic abandonment transactions [backend/database/repositories/users/agent_turn_abandonment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.agent.status_defaults import resolve_agent_turn_terminal_defaults
from core.agent.status_values import AGENT_TURN_STATUS_ABANDONED
from core.errors.exceptions import ValidationError
from database.core.query_execution import (
    sync_fetch_changes_count,
    sync_fetch_one_as_dict,
)
from database.repositories.users.agent_turn_rows import format_agent_turn_row

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_abandon_running_turn_if_current",)


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"Agent turn {field_name} is required.")
    return normalized


def sync_abandon_running_turn_if_current(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    turn_id: str,
    execution_token: str,
    finished_at_ms: int,
) -> JSONDict | None:
    normalized_conv_id = _require_text(conv_id, "conv_id")
    normalized_turn_id = _require_text(turn_id, "turn_id")
    normalized_execution_token = _require_text(execution_token, "execution_token")
    if int(user_id) <= 0:
        raise ValidationError("Agent turn user_id is invalid.")
    if int(finished_at_ms) < 0:
        raise ValidationError("Agent turn finished_at_ms is invalid.")
    terminal_defaults = resolve_agent_turn_terminal_defaults(AGENT_TURN_STATUS_ABANDONED)
    default_error_message = terminal_defaults[1]
    default_error_type = terminal_defaults[2]
    sqlite_conn.execute(
        """
        UPDATE webui_agent_turns
           SET status = ?,
               active_inference_cancellation_id = NULL,
               error_message = COALESCE(error_message, ?),
               error_type = COALESCE(error_type, ?),
               updated_at_ms = ?,
               finished_at_ms = ?
         WHERE conv_id = ?
           AND user_id = ?
           AND turn_id = ?
           AND status = 'running'
           AND execution_token = ?
        """,
        (
            AGENT_TURN_STATUS_ABANDONED,
            default_error_message,
            default_error_type,
            int(finished_at_ms),
            int(finished_at_ms),
            normalized_conv_id,
            int(user_id),
            normalized_turn_id,
            normalized_execution_token,
        ),
    )
    if sync_fetch_changes_count(sqlite_conn) < 1:
        return None
    row = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            """
            SELECT *
            FROM webui_agent_turns
            WHERE conv_id = ? AND user_id = ? AND turn_id = ?
            LIMIT 1
            """,
            (normalized_conv_id, int(user_id), normalized_turn_id),
        ),
    )
    formatted_row = format_agent_turn_row(row)
    if formatted_row is None:
        raise ValidationError("Abandoned agent turn row could not be reloaded.")
    return formatted_row
