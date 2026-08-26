"""SoAI - Automation abandoned run owner-task operations [backend/database/repositories/users/automation_abandoned_run_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.core.query_execution import sync_fetch_all_first_column

__all__ = (
    "sync_list_abandoned_occurrence_owner_task_ids",
    "sync_list_abandoned_run_owner_task_ids",
    "sync_mark_queued_runs_abandoned_for_disabled",
)


def _append_owner_task_id(owner_task_ids: list[str], owner_task_id_value: str | None) -> None:
    if not isinstance(owner_task_id_value, str):
        return
    owner_task_id = owner_task_id_value.strip()
    if owner_task_id and owner_task_id not in owner_task_ids:
        owner_task_ids.append(owner_task_id)


def sync_list_abandoned_run_owner_task_ids(
    conn: sqlite3.Connection,
    *,
    automation_id: str,
    user_id: int,
    status_message: str,
) -> list[str]:
    values = sync_fetch_all_first_column(
        conn.execute(
            """
            SELECT owner_task_id
            FROM automation_runs
            WHERE automation_id = ?
                AND user_id = ?
                AND status = 'abandoned'
                AND status_message = ?
                AND owner_task_id IS NOT NULL
            ORDER BY scheduled_at_ms ASC, id ASC
            """,
            (automation_id, user_id, status_message),
        ),
    )
    owner_task_ids: list[str] = []
    for value in values:
        _append_owner_task_id(owner_task_ids, value if isinstance(value, str) else None)
    return owner_task_ids


def sync_list_abandoned_occurrence_owner_task_ids(
    conn: sqlite3.Connection,
    *,
    automation_id: str,
    user_id: int,
    scheduled_at_ms: int,
    status_message: str,
) -> list[str]:
    values = sync_fetch_all_first_column(
        conn.execute(
            """
            SELECT owner_task_id
            FROM automation_runs
            WHERE automation_id = ?
                AND user_id = ?
                AND scheduled_at_ms = ?
                AND status = 'abandoned'
                AND status_message = ?
                AND owner_task_id IS NOT NULL
            ORDER BY id ASC
            """,
            (automation_id, user_id, scheduled_at_ms, status_message),
        ),
    )
    owner_task_ids: list[str] = []
    for value in values:
        _append_owner_task_id(owner_task_ids, value if isinstance(value, str) else None)
    return owner_task_ids


def sync_mark_queued_runs_abandoned_for_disabled(
    conn: sqlite3.Connection,
    *,
    automation_id: str,
    user_id: int,
    status_message: str,
    finished_at_ms: int,
) -> list[str]:
    values = sync_fetch_all_first_column(
        conn.execute(
            """
            SELECT id
            FROM automation_runs
            WHERE automation_id = ? AND user_id = ? AND status = 'queued'
            ORDER BY scheduled_at_ms ASC, id ASC
            """,
            (automation_id, user_id),
        ),
    )
    run_ids = [value for value in values if isinstance(value, str)]
    if run_ids:
        conn.execute(
            """
            UPDATE automation_runs
            SET status = 'abandoned', status_message = ?, finished_at_ms = ?
            WHERE automation_id = ? AND user_id = ? AND status = 'queued'
            """,
            (status_message, finished_at_ms, automation_id, user_id),
        )
    return run_ids
