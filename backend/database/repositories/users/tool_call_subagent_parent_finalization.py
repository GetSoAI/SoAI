"""SoAI - Subagent parent tool-call terminal transactions [backend/database/repositories/users/tool_call_subagent_parent_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from database.core.query_execution import (
    sync_fetch_changes_count,
    sync_fetch_one_as_dict,
)
from database.repositories.users.tool_call_row_mapping import format_tool_call_row
from database.repositories.users.tool_call_validation import (
    require_non_empty_string_from_row,
    validate_non_negative_integer,
    validate_optional_string,
    validate_required_epoch_ms_integer,
    validate_status,
    validate_status_completed_at_ms_pair,
    validate_terminal_status_error_message,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_finalize_subagent_parent_tool_call_if_unfinished",)

_SUBAGENT_TOOL_NAME = "subagent_spawn"


def sync_finalize_subagent_parent_tool_call_if_unfinished(
    conn: sqlite3.Connection,
    conv_id: str,
    parent_tool_call_id: str,
    parent_turn_id: str,
    parent_iteration_index: int,
    status: str,
    error_message: str | None,
    tool_result: str | None,
    duration_ms: int,
    completed_at_ms: int,
) -> JSONDict | None:
    normalized_conv_id = require_non_empty_string_from_row(conv_id, "conv_id")
    normalized_call_id = require_non_empty_string_from_row(parent_tool_call_id, "call_id")
    normalized_turn_id = require_non_empty_string_from_row(parent_turn_id, "turn_id")
    validated_iteration_index = validate_non_negative_integer(
        parent_iteration_index,
        "iteration_index",
    )
    if validated_iteration_index is None:
        return None
    validated_status = validate_status(
        status,
        operation="subagent parent finalize",
        call_id=normalized_call_id,
    )
    validated_error_message = validate_optional_string(error_message, "error_message")
    validated_error_message = validate_terminal_status_error_message(
        validated_status,
        validated_error_message,
        operation="subagent parent finalize",
        call_id=normalized_call_id,
    )
    validated_duration_ms = validate_non_negative_integer(duration_ms, "duration_ms")
    validated_completed_at_ms = validate_required_epoch_ms_integer(
        completed_at_ms,
        "completed_at_ms",
    )
    validate_status_completed_at_ms_pair(
        validated_status,
        validated_completed_at_ms,
        operation="subagent parent finalize",
        call_id=normalized_call_id,
    )
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT id
            FROM webui_chat_tool_calls
            WHERE conv_id = ?
              AND call_id = ?
              AND turn_id = ?
              AND iteration_index = ?
              AND tool_name = ?
              AND status IN ('pending', 'running')
            ORDER BY created_at_ms DESC, id DESC
            LIMIT 1
            """,
            (
                normalized_conv_id,
                normalized_call_id,
                normalized_turn_id,
                validated_iteration_index,
                _SUBAGENT_TOOL_NAME,
            ),
        ),
    )
    if row is None:
        return None
    storage_call_id = require_non_empty_string_from_row(row.get("id"), "id")
    conn.execute(
        """
        UPDATE webui_chat_tool_calls
           SET status = ?,
               tool_result = COALESCE(?, tool_result),
               error_message = COALESCE(?, error_message),
               duration_ms = COALESCE(?, duration_ms, 0),
               completed_at_ms = COALESCE(?, completed_at_ms)
         WHERE id = ?
           AND status IN ('pending', 'running')
        """,
        (
            validated_status,
            tool_result,
            validated_error_message,
            validated_duration_ms,
            validated_completed_at_ms,
            storage_call_id,
        ),
    )
    if sync_fetch_changes_count(conn) < 1:
        return None
    return format_tool_call_row(
        sync_fetch_one_as_dict(
            conn.execute(
                "SELECT * FROM webui_chat_tool_calls WHERE id = ? LIMIT 1",
                (storage_call_id,),
            ),
        ),
    )
