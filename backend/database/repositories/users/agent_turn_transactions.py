"""SoAI - Agent turn repository transaction logic [backend/database/repositories/users/agent_turn_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.agent.turn_scope_values import TURN_SCOPE_ROOT
from core.database.requests import (
    ClaimAgentTurnStateRequest,
    WriteAgentTurnStateRequest,
)
from core.errors.exceptions import ValidationError
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.agent_turn_existing_row_validation import (
    validate_turn_claim_against_existing_row,
    validate_turn_write_against_existing_row,
)
from database.repositories.users.agent_turn_request_validation import (
    validate_turn_state_request,
)
from database.repositories.users.agent_turn_rows import format_agent_turn_row

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "sync_claim_turn_state",
    "sync_write_turn_state",
)


def _raise_validation_for_integrity_error(exception: sqlite3.IntegrityError) -> None:
    conflict_type, detail = parse_sqlite_integrity_error(exception)
    if conflict_type == "unique" and isinstance(detail, str):
        if "webui_agent_turns.conv_id" in detail and "webui_agent_turns.user_id" in detail:
            raise ValidationError("Agent turn already running.") from exception
    raise ValidationError("Agent turn persistence violates database constraints.") from exception


def load_turn_row(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    turn_id: str,
) -> SQLiteRowDict | None:
    row = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            """
            SELECT *
            FROM webui_agent_turns
            WHERE conv_id = ? AND user_id = ? AND turn_id = ?
            LIMIT 1
            """,
            (conv_id, int(user_id), turn_id),
        ),
    )
    return row


def _write_turn_state_row(
    sqlite_conn: sqlite3.Connection,
    request: WriteAgentTurnStateRequest,
) -> None:
    sqlite_conn.execute(
        """
        INSERT INTO webui_agent_turns (
            conv_id, user_id, turn_id, turn_scope, parent_turn_id, parent_tool_call_id,
            parent_iteration_index, display_name, requested_model, owner_task_id,
            execution_token, server_boot_id, status, mode, max_iterations, iteration_index,
            sequence, turn_cancellation_id, active_inference_cancellation_id, assistant_text,
            tool_calls_json, tool_results_json, activities_json, reached_max_iterations, error_message, error_type,
            token_usage_json, todo_revision, todo_explanation, todo_json, started_at_ms, updated_at_ms, finished_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(conv_id, user_id, turn_id) DO UPDATE SET
            turn_scope = excluded.turn_scope,
            parent_turn_id = excluded.parent_turn_id,
            parent_tool_call_id = excluded.parent_tool_call_id,
            parent_iteration_index = excluded.parent_iteration_index,
            display_name = excluded.display_name,
            requested_model = excluded.requested_model,
            owner_task_id = excluded.owner_task_id,
            execution_token = excluded.execution_token,
            server_boot_id = excluded.server_boot_id,
            status = excluded.status,
            mode = excluded.mode,
            max_iterations = excluded.max_iterations,
            iteration_index = excluded.iteration_index,
            sequence = excluded.sequence,
            turn_cancellation_id = excluded.turn_cancellation_id,
            active_inference_cancellation_id = excluded.active_inference_cancellation_id,
            assistant_text = excluded.assistant_text,
            tool_calls_json = excluded.tool_calls_json,
            tool_results_json = excluded.tool_results_json,
            activities_json = excluded.activities_json,
            reached_max_iterations = excluded.reached_max_iterations,
            error_message = excluded.error_message,
            error_type = excluded.error_type,
            token_usage_json = COALESCE(excluded.token_usage_json, webui_agent_turns.token_usage_json),
            todo_revision = excluded.todo_revision,
            todo_explanation = excluded.todo_explanation,
            todo_json = excluded.todo_json,
            started_at_ms = excluded.started_at_ms,
            updated_at_ms = excluded.updated_at_ms,
            finished_at_ms = excluded.finished_at_ms
        """,
        (
            request.conv_id,
            int(request.user_id),
            request.turn_id,
            request.turn_scope,
            request.parent_turn_id,
            request.parent_tool_call_id,
            request.parent_iteration_index,
            request.display_name,
            request.requested_model,
            request.owner_task_id,
            request.execution_token,
            request.server_boot_id,
            request.status,
            request.mode,
            int(request.max_iterations),
            int(request.iteration_index),
            int(request.sequence),
            request.turn_cancellation_id,
            request.active_inference_cancellation_id,
            request.assistant_text,
            request.tool_calls_json,
            request.tool_results_json,
            request.activities_json,
            1 if request.reached_max_iterations else 0,
            request.error_message,
            request.error_type,
            request.token_usage_json,
            int(request.todo_revision),
            request.todo_explanation,
            request.todo_json,
            int(request.started_at_ms),
            int(request.updated_at_ms),
            request.finished_at_ms,
        ),
    )


def sync_write_turn_state(
    sqlite_conn: sqlite3.Connection,
    request: WriteAgentTurnStateRequest,
) -> JSONDict:
    validate_turn_state_request(request)
    existing_row = load_turn_row(
        sqlite_conn,
        conv_id=request.conv_id,
        user_id=request.user_id,
        turn_id=request.turn_id,
    )
    if existing_row is None:
        raise ValidationError("Agent turn must be claimed before it can be updated.")
    validate_turn_write_against_existing_row(existing_row, request)
    try:
        _write_turn_state_row(sqlite_conn, request)
    except sqlite3.IntegrityError as exception:
        _raise_validation_for_integrity_error(exception)
    persisted_row = load_turn_row(
        sqlite_conn,
        conv_id=request.conv_id,
        user_id=request.user_id,
        turn_id=request.turn_id,
    )
    formatted_row = format_agent_turn_row(persisted_row)
    if formatted_row is None:
        raise ValidationError("Persisted agent turn row could not be reloaded.")
    return formatted_row


def sync_claim_turn_state(
    sqlite_conn: sqlite3.Connection,
    request: ClaimAgentTurnStateRequest,
) -> JSONDict:
    turn_state = request.turn_state
    validate_turn_state_request(turn_state)
    stale_turn_tokens: dict[str, str] = {}
    for stale_turn in request.stale_running_turns:
        stale_turn_id = stale_turn.turn_id.strip()
        stale_execution_token = stale_turn.execution_token.strip()
        if not stale_turn_id or not stale_execution_token or stale_turn_id == turn_state.turn_id:
            raise ValidationError("Agent turn stale-running-turn claim is invalid.")
        stale_turn_tokens[stale_turn_id] = stale_execution_token
    for stale_turn_id, stale_execution_token in stale_turn_tokens.items():
        sqlite_conn.execute(
            """
            UPDATE webui_agent_turns
               SET status = 'abandoned',
                   active_inference_cancellation_id = NULL,
                   updated_at_ms = ?,
                   finished_at_ms = ?
             WHERE conv_id = ?
               AND user_id = ?
               AND turn_id = ?
               AND status = 'running'
               AND execution_token = ?
            """,
            (
                int(turn_state.updated_at_ms),
                int(turn_state.updated_at_ms),
                turn_state.conv_id,
                int(turn_state.user_id),
                stale_turn_id,
                stale_execution_token,
            ),
        )
    running_row = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            f"""
            SELECT turn_id
            FROM webui_agent_turns
            WHERE conv_id = ?
              AND user_id = ?
              AND turn_scope = '{TURN_SCOPE_ROOT}'
              AND status = 'running'
              AND turn_id != ?
            LIMIT 1
            """,
            (turn_state.conv_id, int(turn_state.user_id), turn_state.turn_id),
        ),
    )
    if turn_state.turn_scope == TURN_SCOPE_ROOT and running_row is not None:
        raise ValidationError("Agent turn already running.")
    existing_row = load_turn_row(
        sqlite_conn,
        conv_id=turn_state.conv_id,
        user_id=turn_state.user_id,
        turn_id=turn_state.turn_id,
    )
    if existing_row is not None:
        validate_turn_claim_against_existing_row(existing_row, turn_state)
    try:
        _write_turn_state_row(sqlite_conn, turn_state)
    except sqlite3.IntegrityError as exception:
        _raise_validation_for_integrity_error(exception)
    persisted_row = load_turn_row(
        sqlite_conn,
        conv_id=turn_state.conv_id,
        user_id=turn_state.user_id,
        turn_id=turn_state.turn_id,
    )
    formatted_row = format_agent_turn_row(persisted_row)
    if formatted_row is None:
        raise ValidationError("Persisted agent turn row could not be reloaded.")
    return formatted_row
