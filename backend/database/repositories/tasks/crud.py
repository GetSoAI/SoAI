"""SoAI - Database tasks CRUD operations [backend/database/repositories/tasks/crud.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.database.task_requests import (
    CreateUnifiedTaskRequest,
)
from core.errors.exceptions import TaskConcurrencyLimitError
from core.tasks.status_policy import (
    ACTIVE_TASK_STATUS_VALUES,
    TERMINAL_TASK_STATUS_VALUES,
    active_task_status_placeholders,
    terminal_task_status_placeholders,
)
from core.timing.epoch import epoch_ms
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sql_builders import build_update_statement
from database.core.sqlite_numbers import coerce_required_int_from_sqlite_row
from database.repositories.tasks.conversation_interaction_suspension import (
    sync_suspend_conversation_input_for_interaction,
)
from database.repositories.tasks.mutation_lifecycle import sync_cleanup_expired_mutation_admissions
from database.repositories.tasks.orchestrator_queue_phases import (
    sync_update_queue_phase_for_status,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "sync_cleanup_expired_unified_tasks",
    "sync_create_unified_task",
    "sync_delete_unified_task",
    "sync_update_unified_task_status",
)

_ALLOWED_UNIFIED_TASK_STATUS_UPDATE_COLS = frozenset(
    (
        "status",
        "updated_at_ms",
        "status_message",
        "progress_current",
        "progress_total",
        "progress_details",
    ),
)


def sync_create_unified_task(
    conn: sqlite3.Connection,
    request: CreateUnifiedTaskRequest,
) -> bool:
    existing_task_row = sync_fetch_one_as_dict(
        conn.execute("SELECT task_id FROM unified_tasks WHERE task_id = ?", (request.task_id,)),
    )
    if existing_task_row is not None:
        return False
    if request.max_concurrent is not None:
        row = sync_fetch_one_as_dict(
            conn.execute(
                f"""SELECT COUNT(*) AS count FROM unified_tasks
                   WHERE owner_type = ? AND owner_id = ?
                   AND status IN ({active_task_status_placeholders()})
                   AND cancellation_requested_at_ms IS NULL""",
                (request.owner_type, request.owner_id, *ACTIVE_TASK_STATUS_VALUES),
            ),
        )
        active_count = coerce_required_int_from_sqlite_row(row, "count") if row else 0
        if active_count >= request.max_concurrent:
            raise TaskConcurrencyLimitError(
                request.owner_type,
                request.owner_id,
                request.max_concurrent,
            )
    now = epoch_ms()
    progress_current = 0 if request.progress_total is not None else None
    try:
        conn.execute(
            """INSERT INTO unified_tasks (
                task_id, task_type, status, user_id, owner_id, owner_type,
                cancellation_id, created_at_ms, updated_at_ms, ttl_ms, poll_interval_ms,
                progress_current, progress_total, status_message, metadata, orchestration_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request.task_id,
                request.task_type,
                request.status,
                request.user_id,
                request.owner_id,
                request.owner_type,
                request.cancellation_id,
                now,
                now,
                request.ttl_ms,
                request.poll_interval_ms,
                progress_current,
                request.progress_total,
                request.status_message,
                request.metadata,
                request.orchestration_state,
            ),
        )
    except sqlite3.IntegrityError as exception:
        exception_message = str(exception)
        is_task_id_collision = (
            "UNIQUE constraint failed: unified_tasks.task_id" in exception_message
            or "PRIMARY KEY constraint" in exception_message
        )
        if is_task_id_collision:
            return False
        raise
    if request.interaction_checkpoint is not None:
        sync_suspend_conversation_input_for_interaction(
            conn,
            task_id=request.task_id,
            checkpoint=request.interaction_checkpoint,
            created_at_ms=now,
        )
    return True


def sync_update_unified_task_status(
    conn: sqlite3.Connection,
    task_id: str,
    status: str,
    status_message: str | None = None,
    progress_current: int | None = None,
    progress_total: int | None = None,
    progress_details: str | None = None,
) -> bool:
    now = epoch_ms()
    updates: dict[str, SQLiteValue] = {"status": status, "updated_at_ms": now}
    if status_message is not None:
        updates["status_message"] = status_message
    if progress_current is not None:
        updates["progress_current"] = progress_current
    if progress_total is not None:
        updates["progress_total"] = progress_total
    if progress_details is not None:
        updates["progress_details"] = progress_details
    where_params: list[SQLiteValue] = [task_id]
    where_params.extend(ACTIVE_TASK_STATUS_VALUES)
    sql, params = build_update_statement(
        table="unified_tasks",
        updates=updates,
        where_clause=f"task_id = ? AND status IN ({active_task_status_placeholders()})",
        where_params=tuple(where_params),
        allowed_columns=set(_ALLOWED_UNIFIED_TASK_STATUS_UPDATE_COLS),
    )
    updated = conn.execute(sql, params).rowcount > 0
    if updated:
        sync_update_queue_phase_for_status(conn, task_id, task_status=status)
    return updated


def sync_delete_unified_task(conn: sqlite3.Connection, task_id: str) -> bool:
    return conn.execute("DELETE FROM unified_tasks WHERE task_id = ?", (task_id,)).rowcount > 0


def sync_cleanup_expired_unified_tasks(conn: sqlite3.Connection) -> int:
    now = epoch_ms()
    sync_cleanup_expired_mutation_admissions(conn, now)
    return conn.execute(
        f"""
        DELETE FROM unified_tasks
         WHERE ttl_ms IS NOT NULL
           AND (COALESCE(completed_at_ms, updated_at_ms, created_at_ms) + ttl_ms) < ?
           AND status IN ({terminal_task_status_placeholders()})
           AND NOT EXISTS (
               SELECT 1 FROM mutation_admissions
                WHERE accepted_task_id = unified_tasks.task_id
           )
        """,
        (now, *TERMINAL_TASK_STATUS_VALUES),
    ).rowcount
