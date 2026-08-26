"""SoAI - Automation run claiming transactions [backend/database/repositories/users/automation_claim_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid

from core.automation.automation_recurrence import resolve_due_run_slots_and_next_run_at
from core.errors.exceptions import StateError
from core.types.json import JSONDict
from core.users.user_id import is_strict_user_id
from database.core.query_execution import (
    sync_fetch_all_first_column,
    sync_fetch_one_as_dict,
    sync_fetch_one_scalar,
)
from database.core.sql_builders import build_placeholder_list
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.automation_event_outbox import (
    sync_enqueue_automation_domain_event,
)
from database.repositories.users.automation_row_formatter import format_automation_row
from database.repositories.users.automation_run_row_formatter import (
    format_automation_run_row,
)
from database.repositories.users.automation_sql_support import (
    automation_select_sql,
    fetch_run_row_by_id,
    insert_automation_run,
)

__all__ = ("sync_claim_due_runs",)


def _load_existing_run_for_slot(
    conn: sqlite3.Connection,
    *,
    automation_id: str,
    scheduled_at_ms: int,
) -> JSONDict | None:
    existing_run_id = sync_fetch_one_scalar(
        conn.execute(
            "SELECT id FROM automation_runs WHERE automation_id = ? AND scheduled_at_ms = ?",
            (automation_id, scheduled_at_ms),
        ),
    )
    if not isinstance(existing_run_id, str):
        return None
    formatted = format_automation_run_row(fetch_run_row_by_id(conn, run_id=existing_run_id))
    if formatted is None:
        raise StateError("Existing automation run could not be loaded.")
    return formatted


def _insert_claimed_run(
    conn: sqlite3.Connection,
    *,
    automation: JSONDict,
    automation_id: str,
    now_ms: int,
    scheduled_at_ms: int,
) -> tuple[JSONDict | None, bool]:
    active_run_id = sync_fetch_one_scalar(
        conn.execute(
            (
                "SELECT id FROM automation_runs WHERE automation_id = ? "
                "AND status IN ('queued', 'running') LIMIT 1"
            ),
            (automation_id,),
        ),
    )
    run_id = f"run_{uuid.uuid4().hex}"
    status = "queued" if active_run_id is None else "abandoned"
    status_message = None if active_run_id is None else "overlap"
    finished_at_ms = None if status == "queued" else now_ms
    try:
        insert_automation_run(
            conn,
            automation_record=automation,
            run_id=run_id,
            scheduled_at_ms=scheduled_at_ms,
            status=status,
            status_message=status_message,
            finished_at_ms=finished_at_ms,
        )
    except sqlite3.IntegrityError as exception:
        conflict_type, detail = parse_sqlite_integrity_error(exception)
        if (
            conflict_type == "unique"
            and detail == "automation_runs.automation_id, automation_runs.scheduled_at_ms"
        ):
            return (
                _load_existing_run_for_slot(
                    conn,
                    automation_id=automation_id,
                    scheduled_at_ms=scheduled_at_ms,
                ),
                False,
            )
        if conflict_type == "unique" and detail == "automation_runs.automation_id":
            run_id = f"run_{uuid.uuid4().hex}"
            try:
                insert_automation_run(
                    conn,
                    automation_record=automation,
                    run_id=run_id,
                    scheduled_at_ms=scheduled_at_ms,
                    status="abandoned",
                    status_message="overlap",
                    finished_at_ms=now_ms,
                )
            except sqlite3.IntegrityError as retry_exception:
                retry_conflict_type, retry_detail = parse_sqlite_integrity_error(retry_exception)
                if (
                    retry_conflict_type == "unique"
                    and retry_detail
                    == "automation_runs.automation_id, automation_runs.scheduled_at_ms"
                ):
                    return (
                        _load_existing_run_for_slot(
                            conn,
                            automation_id=automation_id,
                            scheduled_at_ms=scheduled_at_ms,
                        ),
                        False,
                    )
                raise StateError(
                    f"Automation run insert failed: {retry_exception}",
                ) from retry_exception
        else:
            raise StateError(f"Automation run insert failed: {exception}") from exception
    formatted = format_automation_run_row(fetch_run_row_by_id(conn, run_id=run_id))
    return (formatted if isinstance(formatted, dict) else None, True)


def sync_claim_due_runs(
    conn: sqlite3.Connection,
    automation_id: str,
    *,
    now_ms: int,
    expected_next_run_at: int,
    max_run_slots: int,
) -> list[JSONDict]:
    cursor = conn.execute(f"{automation_select_sql()} WHERE id = ?", (automation_id,))
    automation = format_automation_row(sync_fetch_one_as_dict(cursor))
    if not isinstance(automation, dict) or automation.get("enabled") is not True:
        return []
    if automation.get("next_run_at_ms") != expected_next_run_at:
        return []
    due_slots, next_run_at_ms = resolve_due_run_slots_and_next_run_at(
        timezone_name=str(automation["timezone"]),
        start_local=str(automation["start_local"]),
        recurrence=str(automation["recurrence"]),
        first_next_run_at=expected_next_run_at,
        now_ms=now_ms,
        max_slots=max_run_slots,
    )
    if not due_slots:
        return []
    updated = conn.execute(
        (
            "UPDATE automations SET next_run_at_ms = ? "
            "WHERE id = ? AND enabled = 1 AND next_run_at_ms = ?"
        ),
        (next_run_at_ms, automation_id, expected_next_run_at),
    ).rowcount
    if updated != 1:
        return []
    created_runs: list[JSONDict] = []
    user_id = automation.get("user_id")
    if not is_strict_user_id(user_id):
        raise StateError("Automation user_id is invalid.")
    deleted_due_slots: set[int] = set()
    if due_slots:
        placeholders = build_placeholder_list(len(due_slots))
        values = sync_fetch_all_first_column(
            conn.execute(
                f"""
                SELECT scheduled_at_ms
                FROM automation_occurrence_deletions
                WHERE user_id = ? AND automation_id = ? AND scheduled_at_ms IN ({placeholders})
                """,
                (user_id, automation_id, *due_slots),
            ),
        )
        deleted_due_slots = {
            value for value in values if not isinstance(value, bool) and isinstance(value, int)
        }
    for scheduled_at_ms in due_slots:
        if scheduled_at_ms in deleted_due_slots:
            continue
        run_record, created_new = _insert_claimed_run(
            conn,
            automation=automation,
            automation_id=automation_id,
            now_ms=now_ms,
            scheduled_at_ms=scheduled_at_ms,
        )
        if not isinstance(run_record, dict):
            continue
        if created_new:
            sync_enqueue_automation_domain_event(
                conn,
                event_type="AutomationRunCreatedEvent",
                created_at_ms=now_ms,
                user_id=user_id,
                automation_id=automation_id,
                run_id=str(run_record["run_id"]),
            )
        created_runs.append(run_record)
    return created_runs
