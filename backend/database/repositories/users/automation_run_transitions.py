"""SoAI - Automation run state transitions [backend/database/repositories/users/automation_run_transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.types.json import JSONDict
from database.core.query_execution import sync_fetch_all_first_column
from database.repositories.users.automation_run_events import (
    enqueue_run_event,
    enqueue_run_updated_event,
)
from database.repositories.users.automation_run_row_formatter import (
    format_automation_run_row,
)
from database.repositories.users.automation_sql_support import (
    fetch_run_row_by_id,
)

__all__ = (
    "sync_attach_run_conversation",
    "sync_attach_run_owner_task_id",
    "sync_mark_restarted_running_runs",
    "sync_mark_run_running",
)


def sync_mark_run_running(conn: sqlite3.Connection, run_id: str, now_ms: int) -> JSONDict | None:
    if (
        conn.execute(
            (
                "UPDATE automation_runs SET status = 'running', started_at_ms = ?, "
                "finished_at_ms = NULL, status_message = NULL "
                "WHERE id = ? AND status = 'queued'"
            ),
            (now_ms, run_id),
        ).rowcount
        != 1
    ):
        return None
    formatted = format_automation_run_row(fetch_run_row_by_id(conn, run_id=run_id))
    if not isinstance(formatted, dict):
        return None
    enqueue_run_updated_event(
        conn,
        formatted=formatted,
        created_at_ms=now_ms,
        run_id=run_id,
    )
    return formatted


def sync_attach_run_conversation(
    conn: sqlite3.Connection,
    run_id: str,
    user_id: int,
    conv_id: str,
    now_ms: int,
) -> JSONDict | None:
    if (
        conn.execute(
            (
                "UPDATE automation_runs SET conv_id = ?, "
                "started_at_ms = COALESCE(started_at_ms, ?), status_message = NULL "
                "WHERE id = ? AND user_id = ? AND status = 'running' "
                "AND conv_id IS NULL"
            ),
            (conv_id, now_ms, run_id, user_id),
        ).rowcount
        != 1
    ):
        return None
    formatted = format_automation_run_row(fetch_run_row_by_id(conn, run_id=run_id, user_id=user_id))
    if not isinstance(formatted, dict):
        return None
    enqueue_run_event(
        conn,
        event_type="AutomationRunUpdatedEvent",
        created_at_ms=now_ms,
        automation_id=str(formatted["automation_id"]),
        user_id=user_id,
        run_id=run_id,
    )
    return formatted


def sync_attach_run_owner_task_id(
    conn: sqlite3.Connection,
    run_id: str,
    user_id: int,
    owner_task_id: str,
) -> JSONDict | None:
    if (
        conn.execute(
            (
                "UPDATE automation_runs SET owner_task_id = ? "
                "WHERE id = ? AND user_id = ? AND owner_task_id IS NULL "
                "AND status IN ('queued', 'running')"
            ),
            (owner_task_id, run_id, user_id),
        ).rowcount
        != 1
    ):
        return None
    formatted = format_automation_run_row(fetch_run_row_by_id(conn, run_id=run_id, user_id=user_id))
    if not isinstance(formatted, dict):
        return None
    return formatted


def sync_mark_restarted_running_runs(
    conn: sqlite3.Connection,
    now_ms: int,
    status_message: str,
) -> list[JSONDict]:
    values = sync_fetch_all_first_column(
        conn.execute(
            "SELECT id FROM automation_runs WHERE status = 'running' ORDER BY scheduled_at_ms ASC, id ASC",
        ),
    )
    run_ids = [value for value in values if isinstance(value, str)]
    if run_ids:
        conn.execute(
            (
                "UPDATE automation_runs SET status = 'error', "
                "status_message = ?, finished_at_ms = ? WHERE status = 'running'"
            ),
            (status_message, now_ms),
        )
    results: list[JSONDict] = []
    for run_id in run_ids:
        formatted = format_automation_run_row(fetch_run_row_by_id(conn, run_id=run_id))
        if not isinstance(formatted, dict):
            continue
        enqueue_run_updated_event(
            conn,
            formatted=formatted,
            created_at_ms=now_ms,
            run_id=run_id,
        )
        results.append(formatted)
    return results
