"""SoAI - Database tasks backup operations [backend/database/repositories/tasks/backup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.serialization.json import serialize_json_compact_stable_default_str
from core.sqlite.connections import connect_sqlite
from core.tasks.enums import TaskStatus
from core.tasks.status_policy import TERMINAL_TASK_STATUS_VALUES
from core.tasks.type_catalog import TASK_TYPE_BACKUP_RESTORE
from core.timing.epoch import epoch_ms
from core.validation.epoch import require_unix_epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_finalize_restored_backup_task",)


def sync_finalize_restored_backup_task(
    *,
    db_path: str,
    task_id: str,
    user_id: int,
    backup_id: str,
    result: JSONDict,
    success: bool,
    cancellation_id: str | None = None,
    completed_at_ms: int | None = None,
) -> None:
    if not isinstance(db_path, str) or not db_path.strip():
        raise ValidationError("db_path is required.")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValidationError("task_id is required.")
    if not isinstance(backup_id, str) or not backup_id.strip():
        raise ValidationError("backup_id is required.")
    if cancellation_id is not None and (
        not isinstance(cancellation_id, str) or not cancellation_id.strip()
    ):
        raise ValidationError("cancellation_id is required.")
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 1:
        raise ValidationError("user_id must be a positive integer.")
    if not isinstance(result, dict) or not result:
        raise ValidationError("result is required.")
    resolved_completed_at_ms = require_unix_epoch_ms(
        epoch_ms() if completed_at_ms is None else completed_at_ms,
        error_message="completed_at_ms is invalid.",
    )

    status = TaskStatus.COMPLETED.value if success else TaskStatus.FAILED.value
    error_code = None if success else 500
    error_message = None if success else "Restore completed with errors"
    status_message = "Restore complete" if success else "Restore completed with errors"
    metadata_json = serialize_json_compact_stable_default_str(
        {"operation": "restore_backup", "backup_id": backup_id},
    )
    result_json = serialize_json_compact_stable_default_str(result)
    try:
        conn = connect_sqlite(db_path, timeout=60)
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("BEGIN IMMEDIATE;")
            existing = conn.execute(
                """
                SELECT task_type, user_id, owner_id, owner_type, cancellation_id,
                       status, completed_at_ms, result, error_code, error_message
                FROM unified_tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
            resolved_cancellation_id = (
                str(existing[4])
                if cancellation_id is None and existing is not None
                else cancellation_id or f"backup_restore:{backup_id}:{task_id}"
            )
            expected_identity = (
                TASK_TYPE_BACKUP_RESTORE,
                user_id,
                backup_id,
                "system",
                resolved_cancellation_id,
            )
            if existing is not None and tuple(existing[:5]) != expected_identity:
                raise StateError("Restored task ID is bound to a different task identity.")
            if (
                existing is not None
                and existing[5] in TERMINAL_TASK_STATUS_VALUES
                and cancellation_id is not None
                and completed_at_ms is not None
            ):
                try:
                    require_unix_epoch_ms(
                        existing[6],
                        error_message="Restored task completion time is invalid.",
                    )
                except ValidationError as exception:
                    raise StateError("Restored task has an invalid terminal result.") from exception
                expected_terminal = (
                    status,
                    result_json,
                    error_code,
                    error_message,
                )
                actual_terminal = (existing[5], *existing[7:])
                if actual_terminal != expected_terminal:
                    raise StateError("Restored task has a conflicting terminal result.")
                conn.commit()
                return
            conn.execute(
                """
                INSERT INTO unified_tasks (
                    task_id,
                    task_type,
                    status,
                    user_id,
                    owner_id,
                    owner_type,
                    cancellation_id,
                    created_at_ms,
                    updated_at_ms,
                    completed_at_ms,
                    progress_current,
                    progress_total,
                    status_message,
                    metadata,
                    result,
                    error_code,
                    error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO NOTHING
                """,
                (
                    task_id,
                    TASK_TYPE_BACKUP_RESTORE,
                    status,
                    user_id,
                    backup_id,
                    "system",
                    resolved_cancellation_id,
                    resolved_completed_at_ms,
                    resolved_completed_at_ms,
                    resolved_completed_at_ms,
                    100,
                    100,
                    status_message,
                    metadata_json,
                    result_json,
                    error_code,
                    error_message,
                ),
            )
            cursor = conn.execute(
                """
                UPDATE unified_tasks
                SET status = ?,
                    updated_at_ms = ?,
                    completed_at_ms = ?,
                    progress_current = 100,
                    progress_total = 100,
                    status_message = ?,
                    metadata = ?,
                    result = ?,
                    error_code = ?,
                    error_message = ?,
                    orchestration_state = NULL,
                    cancellation_requested_at_ms = NULL
                WHERE task_id = ?
                  AND task_type = ?
                  AND user_id = ?
                  AND owner_id = ?
                  AND owner_type = ?
                  AND cancellation_id = ?
                """,
                (
                    status,
                    resolved_completed_at_ms,
                    resolved_completed_at_ms,
                    status_message,
                    metadata_json,
                    result_json,
                    error_code,
                    error_message,
                    task_id,
                    *expected_identity,
                ),
            )
            if cursor.rowcount != 1:
                raise StateError("Restored task finalization lost its identity binding.")
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as exception:
        raise StateError(
            f"Failed to finalize restore task in restored database: {exception}",
        ) from exception
