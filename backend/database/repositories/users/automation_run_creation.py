"""SoAI - Automation run creation and scheduling [backend/database/repositories/users/automation_run_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid

from core.errors.exceptions import ConflictError, NotFoundError, StateError
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from database.core.query_execution import sync_fetch_one_as_dict, sync_fetch_one_scalar
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.automation_row_formatter import format_automation_row
from database.repositories.users.automation_run_events import enqueue_run_event
from database.repositories.users.automation_run_row_formatter import (
    format_automation_run_row,
)
from database.repositories.users.automation_sql_support import (
    automation_select_sql,
    fetch_run_row_by_id,
    insert_automation_run,
)

__all__ = ("sync_create_run_now",)


def _load_active_run_id(conn: sqlite3.Connection, *, automation_id: str) -> str | None:
    active_run_id = sync_fetch_one_scalar(
        conn.execute(
            (
                "SELECT id FROM automation_runs WHERE automation_id = ? "
                "AND status IN ('queued', 'running') LIMIT 1"
            ),
            (automation_id,),
        ),
    )
    if not isinstance(active_run_id, str):
        return None
    return active_run_id


def _raise_active_run_conflict(
    conn: sqlite3.Connection,
    *,
    automation_id: str,
    exception: sqlite3.IntegrityError,
) -> None:
    active_run_id = _load_active_run_id(conn, automation_id=automation_id)
    details = {"active_run_id": active_run_id} if active_run_id is not None else None
    raise ConflictError("Automation already has an active run.", details=details) from exception


def _next_manual_run_scheduled_at(
    conn: sqlite3.Connection,
    *,
    automation_id: str,
    scheduled_at_ms: int,
) -> int:
    value = sync_fetch_one_scalar(
        conn.execute(
            """
            SELECT MAX(scheduled_at_ms)
            FROM automation_runs
            WHERE automation_id = ? AND scheduled_at_ms >= ?
            """,
            (automation_id, scheduled_at_ms),
        ),
    )
    if not is_strict_int(value):
        return scheduled_at_ms + 1
    return value + 1


def sync_create_run_now(
    conn: sqlite3.Connection,
    automation_id: str,
    user_id: int,
    now_ms: int,
) -> JSONDict:
    cursor = conn.execute(
        f"{automation_select_sql()} WHERE id = ? AND user_id = ?",
        (automation_id, user_id),
    )
    automation = format_automation_row(sync_fetch_one_as_dict(cursor))
    if not isinstance(automation, dict):
        raise NotFoundError("Automation not found.")
    scheduled_at_ms = now_ms
    while True:
        run_id = f"run_{uuid.uuid4().hex}"
        try:
            insert_automation_run(
                conn,
                automation_record=automation,
                run_id=run_id,
                scheduled_at_ms=scheduled_at_ms,
                status="queued",
                status_message=None,
                finished_at_ms=None,
            )
            break
        except sqlite3.IntegrityError as exception:
            conflict_type, detail = parse_sqlite_integrity_error(exception)
            if conflict_type == "unique" and detail == "automation_runs.automation_id":
                _raise_active_run_conflict(conn, automation_id=automation_id, exception=exception)
            if (
                conflict_type == "unique"
                and detail == "automation_runs.automation_id, automation_runs.scheduled_at_ms"
            ):
                scheduled_at_ms = _next_manual_run_scheduled_at(
                    conn,
                    automation_id=automation_id,
                    scheduled_at_ms=scheduled_at_ms,
                )
                continue
            raise StateError(f"Automation run insert failed: {exception}") from exception
    formatted = format_automation_run_row(fetch_run_row_by_id(conn, run_id=run_id, user_id=user_id))
    if not isinstance(formatted, dict):
        raise StateError("Created automation run could not be loaded.")
    enqueue_run_event(
        conn,
        event_type="AutomationRunCreatedEvent",
        created_at_ms=now_ms,
        automation_id=automation_id,
        user_id=user_id,
        run_id=run_id,
    )
    return formatted
