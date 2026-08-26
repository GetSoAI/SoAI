"""SoAI - Tool call insert conflict ownership rules [backend/database/repositories/users/tool_call_insert_conflicts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.database.requests import CreateToolCallRequest, CreateToolCallResult
from core.errors.exceptions import ConflictError, StateError
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_PENDING,
    is_terminal_tool_call_status,
)
from database.repositories.users.context_compaction_metric_events import (
    sync_record_context_compaction_metric_event,
)
from database.repositories.users.tool_call_insert_identity import (
    ValidatedToolCallInsertFields,
    load_tool_call_by_storage_id,
    validate_loaded_tool_call_matches_insert,
    validate_loaded_tool_call_matches_insert_allowing_unknown_arguments,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("resolve_tool_call_insert_conflict",)

UNCLAIMED_PENDING_TOOL_CALL_SQL_FILTER = """
          AND status = ?
          AND started_at_ms IS NULL
          AND tool_result IS NULL
          AND error_message IS NULL
          AND completed_at_ms IS NULL
"""


def resolve_tool_call_insert_conflict(
    conn: sqlite3.Connection,
    *,
    request: CreateToolCallRequest,
    fields: ValidatedToolCallInsertFields,
    status: str,
    error_message: str | None,
    duration_ms: int,
    started_at_ms: int | None,
    completed_at_ms: int | None,
) -> CreateToolCallResult:
    formatted = load_tool_call_by_storage_id(conn, fields.storage_call_id)
    validate_loaded_tool_call_matches_insert_allowing_unknown_arguments(formatted, fields)
    if formatted.get("arguments") is None and fields.tool_arguments is not None:
        conn.execute(
            """UPDATE webui_chat_tool_calls
            SET tool_arguments = ?
            WHERE id = ? AND tool_arguments IS NULL
            """,
            (fields.tool_arguments, fields.storage_call_id),
        )
        formatted = load_tool_call_by_storage_id(conn, fields.storage_call_id)
        validate_loaded_tool_call_matches_insert(formatted, fields)
    if request.exclusive_claim:
        return _claim_existing_tool_call(
            conn,
            fields=fields,
            status=status,
            started_at_ms=started_at_ms,
        )
    if is_terminal_tool_call_status(status):
        return _resolve_terminal_insert_conflict(
            conn,
            fields=fields,
            formatted=formatted,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
            tool_result=request.tool_result,
            completed_at_ms=completed_at_ms,
        )
    return CreateToolCallResult(row=formatted, inserted=False, claimed_existing=False)


def _claim_existing_tool_call(
    conn: sqlite3.Connection,
    *,
    fields: ValidatedToolCallInsertFields,
    status: str,
    started_at_ms: int | None,
) -> CreateToolCallResult:
    if started_at_ms is None:
        raise ConflictError("Tool call claim requires a start timestamp.")
    cursor = conn.execute(
        f"""UPDATE webui_chat_tool_calls
        SET status = ?, started_at_ms = ?
        WHERE id = ?
{UNCLAIMED_PENDING_TOOL_CALL_SQL_FILTER}
        """,
        (
            status,
            started_at_ms,
            fields.storage_call_id,
            TOOL_CALL_STATUS_PENDING,
        ),
    )
    if cursor.rowcount != 1:
        raise ConflictError("Tool call is already claimed.")
    formatted = load_tool_call_by_storage_id(conn, fields.storage_call_id)
    validate_loaded_tool_call_matches_insert(formatted, fields)
    return CreateToolCallResult(row=formatted, inserted=False, claimed_existing=True)


def _resolve_terminal_insert_conflict(
    conn: sqlite3.Connection,
    *,
    fields: ValidatedToolCallInsertFields,
    formatted: JSONDict,
    status: str,
    error_message: str | None,
    duration_ms: int,
    tool_result: str | None,
    completed_at_ms: int | None,
) -> CreateToolCallResult:
    if is_terminal_tool_call_status(str(formatted.get("status") or "")):
        sync_record_context_compaction_metric_event(conn, formatted)
        return CreateToolCallResult(row=formatted, inserted=False, claimed_existing=False)
    if completed_at_ms is None:
        raise StateError("Terminal tool call insert requires completed_at_ms.")
    cursor = conn.execute(
        f"""UPDATE webui_chat_tool_calls
        SET status = ?,
            tool_result = ?,
            error_message = ?,
            duration_ms = ?,
            completed_at_ms = ?
        WHERE id = ?
{UNCLAIMED_PENDING_TOOL_CALL_SQL_FILTER}
        """,
        (
            status,
            tool_result,
            error_message,
            duration_ms,
            completed_at_ms,
            fields.storage_call_id,
            TOOL_CALL_STATUS_PENDING,
        ),
    )
    if cursor.rowcount != 1:
        raise ConflictError("Tool call is already claimed.")
    claimed = load_tool_call_by_storage_id(conn, fields.storage_call_id)
    validate_loaded_tool_call_matches_insert(claimed, fields)
    sync_record_context_compaction_metric_event(conn, claimed)
    return CreateToolCallResult(row=claimed, inserted=False, claimed_existing=True)
