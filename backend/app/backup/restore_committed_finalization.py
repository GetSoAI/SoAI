"""SoAI - Durable committed restore task finalization [backend/app/backup/restore_committed_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from app.backup.restore_journal import RestoreCompletionRecord
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import StateError
from core.sqlite.file_permissions import secure_sqlite_file_permissions
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.type_catalog import TASK_TYPE_BACKUP_RESTORE
from database.repositories.tasks.backup import sync_finalize_restored_backup_task

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task

__all__ = ("finalize_committed_restore_record",)


def _validate_registry_task_identity(
    task: Task,
    record: RestoreCompletionRecord,
) -> None:
    if (
        task.task_type != TASK_TYPE_BACKUP_RESTORE
        or task.user_id != record.user_id
        or task.owner_id != record.backup_id
        or task.owner_type != "system"
        or task.cancellation_id != record.cancellation_id
    ):
        raise StateError("Committed restore task identity changed during finalization.")


def _validate_finalized_registry_task(
    task: Task,
    record: RestoreCompletionRecord,
) -> None:
    _validate_registry_task_identity(task, record)
    if task.status != TaskStatus.COMPLETED or dict(task.result or {}) != record.result:
        raise StateError("Committed restore task has a conflicting terminal result.")


async def _finalize_record_in_database(record: RestoreCompletionRecord) -> None:
    await run_joined_thread_call(
        secure_sqlite_file_permissions,
        record.database_path,
        task_name="backup-restore-completion-database-permissions",
    )
    await run_joined_thread_call(
        partial(
            sync_finalize_restored_backup_task,
            db_path=record.database_path,
            task_id=record.task_id,
            user_id=record.user_id,
            backup_id=record.backup_id,
            cancellation_id=record.cancellation_id,
            completed_at_ms=record.completed_at_ms,
            result=record.result,
            success=True,
        ),
        task_name="backup-restore-completion-database-task-finalize",
    )
    await run_joined_thread_call(
        secure_sqlite_file_permissions,
        record.database_path,
        task_name="backup-restore-completion-database-permissions",
    )


async def finalize_committed_restore_record(
    record: RestoreCompletionRecord,
    *,
    registry: TaskRegistryProtocol | None,
) -> bool:
    if registry is not None and not record.database_was_shutdown:
        existing = await registry.get(record.task_id)
        if existing is not None:
            _validate_registry_task_identity(existing, record)
            task = await finalize(
                registry,
                record.task_id,
                TaskStatus.COMPLETED,
                prefetched_task=existing,
                result=record.result,
            )
            if task is None:
                raise StateError("Committed restore task disappeared during finalization.")
            _validate_finalized_registry_task(task, record)
            return True
    await _finalize_record_in_database(record)
    return False
