"""SoAI - Ordered background Response finalization from terminal tasks [backend/database/repositories/openai_responses/background_task_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.openai.response_terminal_policy import (
    coerce_response_status,
    is_terminal_response_payload,
    is_terminal_response_status,
)
from core.openai.responses_events import build_response_event_from_json
from core.serialization.json import serialize_json_compact_stable
from database.core.json_codec import safe_json_deserialize_required_object
from database.core.query_execution import sync_fetch_all_as_dicts, sync_fetch_one_as_dict
from database.core.sqlite_numbers import (
    coerce_optional_int_from_sqlite_row,
    coerce_optional_str_from_sqlite_row,
    coerce_required_int_from_sqlite_row,
    coerce_required_nonempty_str_from_sqlite_row,
)
from database.repositories.openai_responses.background_terminal_payload import (
    build_background_response_terminal_payload,
)
from database.repositories.openai_responses.write_ops_events import sync_append_event
from database.repositories.openai_responses.write_ops_shared import (
    read_next_response_event_sequence,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "sync_reconcile_all_terminal_background_responses",
    "sync_reconcile_terminal_background_response",
)

_TERMINAL_TASK_PROJECTION = (
    "task_id, status, result, error_code, error_type, error_message, "
    "status_message, completed_at_ms"
)
_QUALIFIED_TERMINAL_TASK_PROJECTION = (
    "tasks.task_id, tasks.status, tasks.result, tasks.error_code, tasks.error_type, "
    "tasks.error_message, tasks.status_message, tasks.completed_at_ms"
)


def _sync_finalize_linked_background_responses(
    connection: sqlite3.Connection,
    *,
    task_id: str,
    task_status: str,
    result: str | None,
    error_code: int | None,
    error_type: str | None,
    error_message: str | None,
    status_message: str | None,
    completed_at_ms: int,
) -> int:
    rows = sync_fetch_all_as_dicts(
        connection.execute(
            """
            SELECT response_id, model, created_at_ms, status, response_json
            FROM openai_responses
            WHERE task_id = ?
              AND is_background = 1
            """,
            (task_id,),
        ),
    )
    finalized_count = 0
    for row in rows:
        current_status = coerce_required_nonempty_str_from_sqlite_row(row, "status")
        response_id = coerce_required_nonempty_str_from_sqlite_row(row, "response_id")
        response_json = build_background_response_terminal_payload(
            response_id=response_id,
            model=coerce_required_nonempty_str_from_sqlite_row(row, "model"),
            created_at=coerce_required_int_from_sqlite_row(row, "created_at_ms") // 1000,
            task_status=task_status,
            result=result,
            error_code=error_code,
            error_type=error_type,
            error_message=error_message,
            status_message=status_message,
        )
        target_status = coerce_response_status(
            response_json.get("status"),
            default_status="",
        )
        if not is_terminal_response_status(target_status):
            raise StateError("Background Response projection produced a nonterminal status.")
        current_response_json = safe_json_deserialize_required_object(
            row["response_json"],
            error_message="Stored background Response payload must be a JSON object.",
        )
        event_json = build_response_event_from_json(
            response_json=response_json,
            default_status=target_status,
        )
        terminal_event_is_canonical = _terminal_event_state_is_canonical(
            connection,
            response_id=response_id,
            expected_event=event_json,
        )
        if (
            current_status == target_status
            and current_response_json == response_json
            and terminal_event_is_canonical
        ):
            continue
        updated = connection.execute(
            """
            UPDATE openai_responses
            SET status = ?, response_json = ?
            WHERE response_id = ?
              AND status = ?
            """,
            (
                target_status,
                serialize_json_compact_stable(response_json),
                response_id,
                current_status,
            ),
        ).rowcount
        if updated != 1:
            raise StateError("Background response changed during terminal task projection.")
        _delete_terminal_response_events(connection, response_id=response_id)
        sequence = read_next_response_event_sequence(connection, response_id=response_id)
        event_json["sequence_number"] = sequence
        sync_append_event(
            connection,
            response_id,
            sequence,
            event_json,
            completed_at_ms,
        )
        finalized_count += 1
    return finalized_count


def sync_reconcile_all_terminal_background_responses(
    connection: sqlite3.Connection,
) -> int:
    task_rows = sync_fetch_all_as_dicts(
        connection.execute(f"""
            SELECT DISTINCT {_QUALIFIED_TERMINAL_TASK_PROJECTION}
            FROM unified_tasks AS tasks
            JOIN openai_responses AS responses ON responses.task_id = tasks.task_id
            WHERE tasks.status IN ('completed', 'failed', 'cancelled')
              AND responses.is_background = 1
            """),
    )
    reconciled_count = 0
    for row in task_rows:
        reconciled_count += _reconcile_task_row(connection, row=row)
    return reconciled_count


def sync_reconcile_terminal_background_response(
    connection: sqlite3.Connection,
    task_id: str,
) -> int:
    row = sync_fetch_one_as_dict(
        connection.execute(
            f"""
            SELECT {_TERMINAL_TASK_PROJECTION}
            FROM unified_tasks
            WHERE task_id = ? AND status IN ('completed', 'failed', 'cancelled')
            LIMIT 1
            """,
            (task_id,),
        )
    )
    if row is None:
        return 0
    return _reconcile_task_row(connection, row=row)


def _reconcile_task_row(connection: sqlite3.Connection, *, row: SQLiteRowDict) -> int:
    return _sync_finalize_linked_background_responses(
        connection,
        task_id=coerce_required_nonempty_str_from_sqlite_row(row, "task_id"),
        task_status=coerce_required_nonempty_str_from_sqlite_row(row, "status"),
        result=coerce_optional_str_from_sqlite_row(row, "result"),
        error_code=coerce_optional_int_from_sqlite_row(row, "error_code"),
        error_type=coerce_optional_str_from_sqlite_row(row, "error_type"),
        error_message=coerce_optional_str_from_sqlite_row(row, "error_message"),
        status_message=coerce_optional_str_from_sqlite_row(row, "status_message"),
        completed_at_ms=coerce_required_int_from_sqlite_row(row, "completed_at_ms"),
    )


def _terminal_event_state_is_canonical(
    connection: sqlite3.Connection,
    *,
    response_id: str,
    expected_event: JSONDict,
) -> bool:
    rows = sync_fetch_all_as_dicts(
        connection.execute(
            "SELECT sequence, event_json FROM openai_response_events WHERE response_id = ?",
            (response_id,),
        )
    )
    terminal_event_count = 0
    canonical_event_count = 0
    canonical_terminal_sequence: int | None = None
    maximum_sequence = -1
    for row in rows:
        sequence = coerce_required_int_from_sqlite_row(row, "sequence")
        maximum_sequence = max(maximum_sequence, sequence)
        event_json = safe_json_deserialize_required_object(
            row["event_json"],
            error_message="Stored background Response event must be a JSON object.",
        )
        if not is_terminal_response_payload(event_json):
            continue
        terminal_event_count += 1
        canonical_event = dict(expected_event)
        canonical_event["sequence_number"] = sequence
        if event_json == canonical_event:
            canonical_event_count += 1
            canonical_terminal_sequence = sequence
    return (
        terminal_event_count == 1
        and canonical_event_count == 1
        and canonical_terminal_sequence == maximum_sequence
    )


def _delete_terminal_response_events(
    connection: sqlite3.Connection,
    *,
    response_id: str,
) -> None:
    rows = sync_fetch_all_as_dicts(
        connection.execute(
            "SELECT sequence, event_json FROM openai_response_events WHERE response_id = ?",
            (response_id,),
        )
    )
    for row in rows:
        event_json = safe_json_deserialize_required_object(
            row["event_json"],
            error_message="Stored background Response event must be a JSON object.",
        )
        if not is_terminal_response_payload(event_json):
            continue
        sequence = coerce_required_int_from_sqlite_row(row, "sequence")
        deleted = connection.execute(
            "DELETE FROM openai_response_events WHERE response_id = ? AND sequence = ?",
            (response_id, sequence),
        ).rowcount
        if deleted != 1:
            raise StateError("Background response terminal event changed during reconciliation.")
