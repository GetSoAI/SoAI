"""SoAI - Tool call repository state transactions [backend/database/repositories/users/tool_call_state_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.tool_calls.status_values import (
    is_active_tool_call_status,
    is_terminal_tool_call_status,
    resolve_tool_call_status_rank,
)
from core.types.json import JSONDict
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.context_compaction_metric_events import (
    sync_record_context_compaction_metric_event,
)
from database.repositories.users.tool_call_identity_queries import (
    build_tool_call_identity_query,
)
from database.repositories.users.tool_call_owner_task_binding import (
    resolve_tool_call_owner_task_binding,
)
from database.repositories.users.tool_call_row_mapping import format_tool_call_row
from database.repositories.users.tool_call_validation import (
    require_non_empty_string_from_row,
    validate_optional_string,
    validate_required_epoch_ms_integer,
    validate_status,
    validate_status_completed_at_ms_pair,
    validate_terminal_status_error_message,
    validate_tool_call_write_fields,
)

__all__ = (
    "sync_finalize_tool_call_if_unfinished",
    "sync_finalize_tool_call_if_unfinished_by_identity",
    "sync_finalize_active_tool_call_with_result",
    "sync_update_tool_call",
)


def sync_finalize_active_tool_call_with_result(
    conn: sqlite3.Connection,
    storage_call_id: str,
    status: str,
    tool_result: str,
    error_message: str | None,
    duration_ms: int,
    completed_at_ms: int,
) -> JSONDict | None:
    normalized_storage_call_id = require_non_empty_string_from_row(storage_call_id, "call_id")
    validated_fields = validate_tool_call_write_fields(
        status=status,
        error_message=error_message,
        duration_ms=duration_ms,
        started_at_ms=None,
        completed_at_ms=completed_at_ms,
        operation="finalize active with result",
        call_id=normalized_storage_call_id,
    )
    update_cursor = conn.execute(
        "UPDATE webui_chat_tool_calls SET status = ?, tool_result = ?, error_message = ?, duration_ms = ?, completed_at_ms = ? WHERE id = ? AND status IN ('pending', 'running')",
        (
            validated_fields.status,
            tool_result,
            validated_fields.error_message,
            validated_fields.duration_ms,
            validated_fields.completed_at_ms,
            normalized_storage_call_id,
        ),
    )
    cursor = conn.execute(
        "SELECT * FROM webui_chat_tool_calls WHERE id = ?",
        (normalized_storage_call_id,),
    )
    formatted = format_tool_call_row(sync_fetch_one_as_dict(cursor))
    if update_cursor.rowcount > 0:
        sync_record_context_compaction_metric_event(conn, formatted)
    return formatted


def sync_update_tool_call(
    conn: sqlite3.Connection,
    storage_call_id: str,
    status: str | None,
    tool_result: str | None,
    error_message: str | None,
    duration_ms: int | None,
    started_at_ms: int | None,
    completed_at_ms: int | None,
    owner_task_id: str | None = None,
) -> JSONDict | None:
    normalized_storage_call_id = require_non_empty_string_from_row(storage_call_id, "call_id")
    validated_fields = validate_tool_call_write_fields(
        status=status,
        error_message=error_message,
        duration_ms=duration_ms,
        started_at_ms=started_at_ms,
        completed_at_ms=completed_at_ms,
        operation="update",
        call_id=normalized_storage_call_id,
    )
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT status, tool_result, owner_task_id FROM webui_chat_tool_calls WHERE id = ?",
            (normalized_storage_call_id,),
        ),
    )
    if row is None:
        return None
    owner_binding = resolve_tool_call_owner_task_binding(
        requested_owner_task_id=owner_task_id,
        current_owner_task_id=row.get("owner_task_id"),
    )
    current_status = require_non_empty_string_from_row(row.get("status"), "status")
    current_status = validate_status(
        current_status,
        operation="update current",
        call_id=normalized_storage_call_id,
    )
    apply_status_update = (
        validated_fields.status is not None
        and is_active_tool_call_status(current_status)
        and resolve_tool_call_status_rank(validated_fields.status)
        >= resolve_tool_call_status_rank(current_status)
    )
    apply_active_field_update = apply_status_update or (
        validated_fields.status is None and is_active_tool_call_status(current_status)
    )
    apply_missing_terminal_payload_update = (
        validated_fields.status is not None
        and current_status == validated_fields.status
        and is_terminal_tool_call_status(current_status)
        and row.get("tool_result") is None
    )
    apply_owner_task_update = owner_binding.apply_update and apply_active_field_update
    conn.execute(
        """
        UPDATE webui_chat_tool_calls
        SET
            status = CASE WHEN ? THEN ? ELSE status END,
            tool_result = CASE
                WHEN ? THEN COALESCE(?, tool_result)
                WHEN ? THEN COALESCE(tool_result, ?)
                ELSE tool_result
            END,
            error_message = CASE
                WHEN ? THEN COALESCE(?, error_message)
                WHEN ? THEN COALESCE(error_message, ?)
                ELSE error_message
            END,
            duration_ms = CASE
                WHEN ? THEN COALESCE(?, duration_ms, 0)
                WHEN ? THEN COALESCE(duration_ms, ?, 0)
                ELSE duration_ms
            END,
            started_at_ms = CASE WHEN ? THEN COALESCE(?, started_at_ms) ELSE started_at_ms END,
            owner_task_id = CASE WHEN ? THEN ? ELSE owner_task_id END,
            completed_at_ms = CASE
                WHEN ? THEN COALESCE(?, completed_at_ms)
                WHEN ? THEN COALESCE(completed_at_ms, ?)
                ELSE completed_at_ms
            END
        WHERE id = ?
          AND (? = 0 OR ? = 1 OR status IN ('pending', 'running'))
        """,
        (
            apply_status_update,
            validated_fields.status,
            apply_active_field_update,
            tool_result,
            apply_missing_terminal_payload_update,
            tool_result,
            apply_active_field_update,
            validated_fields.error_message,
            apply_missing_terminal_payload_update,
            validated_fields.error_message,
            apply_active_field_update,
            validated_fields.duration_ms,
            apply_missing_terminal_payload_update,
            validated_fields.duration_ms,
            apply_active_field_update,
            validated_fields.started_at_ms,
            apply_owner_task_update,
            owner_binding.owner_task_id,
            apply_active_field_update,
            validated_fields.completed_at_ms,
            apply_missing_terminal_payload_update,
            validated_fields.completed_at_ms,
            normalized_storage_call_id,
            apply_active_field_update,
            apply_missing_terminal_payload_update,
        ),
    )
    cursor = conn.execute(
        "SELECT * FROM webui_chat_tool_calls WHERE id = ?",
        (normalized_storage_call_id,),
    )
    formatted = format_tool_call_row(sync_fetch_one_as_dict(cursor))
    sync_record_context_compaction_metric_event(conn, formatted)
    return formatted


def sync_finalize_tool_call_if_unfinished(
    conn: sqlite3.Connection,
    storage_call_id: str,
    status: str,
    error_message: str | None,
    completed_at_ms: int,
) -> JSONDict | None:
    normalized_storage_call_id = require_non_empty_string_from_row(storage_call_id, "call_id")
    validated_status = validate_status(
        status,
        operation="finalize",
        call_id=normalized_storage_call_id,
    )
    validated_error_message = validate_optional_string(error_message, "error_message")
    validated_error_message = validate_terminal_status_error_message(
        validated_status,
        validated_error_message,
        operation="finalize",
        call_id=normalized_storage_call_id,
    )
    validated_completed_at_ms = validate_required_epoch_ms_integer(
        completed_at_ms,
        "completed_at_ms",
    )
    validate_status_completed_at_ms_pair(
        validated_status,
        validated_completed_at_ms,
        operation="finalize",
        call_id=normalized_storage_call_id,
    )
    conn.execute(
        """
        UPDATE webui_chat_tool_calls
        SET
            status = ?,
            error_message = COALESCE(?, error_message),
            completed_at_ms = COALESCE(?, completed_at_ms)
        WHERE id = ?
          AND status IN ('pending', 'running')
        """,
        (
            validated_status,
            validated_error_message,
            validated_completed_at_ms,
            normalized_storage_call_id,
        ),
    )
    cursor = conn.execute(
        "SELECT * FROM webui_chat_tool_calls WHERE id = ?",
        (normalized_storage_call_id,),
    )
    formatted = format_tool_call_row(sync_fetch_one_as_dict(cursor))
    sync_record_context_compaction_metric_event(conn, formatted)
    return formatted


def sync_finalize_tool_call_if_unfinished_by_identity(
    conn: sqlite3.Connection,
    conv_id: str,
    call_id: str,
    turn_id: str | None,
    iteration_index: int | None,
    message_index: int | None,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    status: str,
    error_message: str | None,
    completed_at_ms: int,
) -> JSONDict | None:
    query, query_params = build_tool_call_identity_query(
        conv_id=conv_id,
        call_id=call_id,
        turn_id=turn_id,
        iteration_index=iteration_index,
        message_index=message_index,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
    )
    row = sync_fetch_one_as_dict(conn.execute(query, query_params))
    if row is None:
        return None
    storage_call_id = require_non_empty_string_from_row(row.get("id"), "id")
    return sync_finalize_tool_call_if_unfinished(
        conn,
        storage_call_id,
        status,
        error_message,
        completed_at_ms,
    )
