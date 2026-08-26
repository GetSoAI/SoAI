"""SoAI - Backup task launching orchestration [backend/app/backup/task_launching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.backup.backup_locking import resolve_backup_path
from app.backup.backup_task_registry import create_task_record, track_operation_task
from app.backup.restore_task_runner import run_restore_backup_task
from app.backup.restore_validation import prepare_restore_preflight
from app.backup.task_create import run_create_backup_task
from app.backup.task_delete import run_delete_backup_task
from app.backup.task_verify import run_verify_backup_task
from core.backup.manifest import validate_backup_id
from core.errors.exceptions import NotFoundError, StateError
from core.filesystem.async_queries import async_isdir
from core.logging.trace import get_logger
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.type_catalog import (
    TASK_TYPE_BACKUP_CREATE,
    TASK_TYPE_BACKUP_DELETE,
    TASK_TYPE_BACKUP_RESTORE,
    TASK_TYPE_BACKUP_VERIFY,
)

if TYPE_CHECKING:
    from app.backup.internal_protocols import (
        BackupRuntimeDependenciesProtocol,
        BackupServiceContext,
        RestoreTaskRunnerContext,
    )

__all__ = (
    "launch_create_backup_task",
    "launch_delete_backup_task",
    "launch_restore_backup_task",
    "launch_verify_backup_task",
)

LOGGER_NAME = "SoAI.app.backup.task_launching"


async def launch_create_backup_task(
    context: BackupServiceContext,
    runtime_deps: BackupRuntimeDependenciesProtocol,
    operation_tasks: set[asyncio.Task[None]],
    user_id: int,
) -> str:
    logger = get_logger(LOGGER_NAME)
    context.require_operational()
    task = await create_task_record(
        task_registry=runtime_deps.task_registry,
        task_type=TASK_TYPE_BACKUP_CREATE,
        user_id=int(user_id),
        owner_id="backup_service",
        metadata={"operation": "create_backup"},
        status_message="Backup started",
    )
    task_id = task.task_id

    async def _create_task() -> None:
        await run_create_backup_task(
            context,
            task_id=task_id,
            user_id=int(user_id),
            operation="create_backup",
        )

    operation_task = spawn_tracked_task(
        _create_task(),
        name=f"backup-create-{task_id}",
        logger=logger,
        cancellation_binder=runtime_deps.task_cancellation_binder,
        cancellation_id=task.cancellation_id,
        owner="backup_create",
        finalizer_tracker=runtime_deps.task_finalizer_tracker,
    )
    track_operation_task(operation_tasks, operation_task)
    return task_id


async def launch_verify_backup_task(
    context: BackupServiceContext,
    runtime_deps: BackupRuntimeDependenciesProtocol,
    operation_tasks: set[asyncio.Task[None]],
    backup_id: str,
    user_id: int,
) -> str:
    logger = get_logger(LOGGER_NAME)
    context.require_operational()
    normalized_backup_id = validate_backup_id(backup_id)
    task = await create_task_record(
        task_registry=runtime_deps.task_registry,
        task_type=TASK_TYPE_BACKUP_VERIFY,
        user_id=int(user_id),
        owner_id=normalized_backup_id,
        metadata={"operation": "verify_backup", "backup_id": normalized_backup_id},
        status_message="Backup verification started",
    )
    task_id = task.task_id
    operation_task = spawn_tracked_task(
        run_verify_backup_task(
            context,
            task_id=task_id,
            backup_id=normalized_backup_id,
            user_id=int(user_id),
        ),
        name=f"backup-verify-{task_id}",
        logger=logger,
        cancellation_binder=runtime_deps.task_cancellation_binder,
        cancellation_id=task.cancellation_id,
        owner="backup_verify",
        finalizer_tracker=runtime_deps.task_finalizer_tracker,
    )
    track_operation_task(operation_tasks, operation_task)
    return task_id


async def launch_delete_backup_task(
    context: BackupServiceContext,
    runtime_deps: BackupRuntimeDependenciesProtocol,
    operation_tasks: set[asyncio.Task[None]],
    backups_path: str,
    backup_id: str,
    user_id: int,
) -> str:
    logger = get_logger(LOGGER_NAME)
    context.require_operational()
    if not backups_path:
        raise StateError("Backups path is not configured.")
    normalized_backup_id = validate_backup_id(backup_id)
    backup_path = resolve_backup_path(backups_path, normalized_backup_id)
    if not await async_isdir(backup_path):
        raise NotFoundError(
            f"Backup '{normalized_backup_id}' not found.",
            details={"backup_id": normalized_backup_id},
        )
    task = await create_task_record(
        task_registry=runtime_deps.task_registry,
        task_type=TASK_TYPE_BACKUP_DELETE,
        user_id=int(user_id),
        owner_id=normalized_backup_id,
        metadata={"operation": "delete_backup", "backup_id": normalized_backup_id},
        status_message="Backup deletion started",
    )
    task_id = task.task_id
    operation_task = spawn_tracked_task(
        run_delete_backup_task(
            context,
            task_id=task_id,
            backup_id=normalized_backup_id,
            user_id=int(user_id),
        ),
        name=f"backup-delete-{task_id}",
        logger=logger,
        cancellation_binder=runtime_deps.task_cancellation_binder,
        cancellation_id=task.cancellation_id,
        owner="backup_delete",
        finalizer_tracker=runtime_deps.task_finalizer_tracker,
    )
    track_operation_task(operation_tasks, operation_task)
    return task_id


async def launch_restore_backup_task(
    context: RestoreTaskRunnerContext,
    runtime_deps: BackupRuntimeDependenciesProtocol,
    operation_tasks: set[asyncio.Task[None]],
    backup_id: str,
    user_id: int,
) -> str:
    logger = get_logger(LOGGER_NAME)
    context.require_operational()
    backups_path = context.backups_path
    preflight = await prepare_restore_preflight(
        backup_id=backup_id,
        backups_path=backups_path,
        config=context.config,
        files=context.files,
        log=logger,
    )
    task = await create_task_record(
        task_registry=runtime_deps.task_registry,
        task_type=TASK_TYPE_BACKUP_RESTORE,
        user_id=int(user_id),
        owner_id=preflight.backup_id,
        metadata={"operation": "restore_backup", "backup_id": preflight.backup_id},
        status_message="Restore started",
    )
    task_id = task.task_id
    operation_task = spawn_tracked_task(
        run_restore_backup_task(
            context,
            task_id,
            preflight.backup_id,
            user_id=int(user_id),
            cancellation_id=task.cancellation_id,
        ),
        name=f"backup-restore-{task_id}",
        logger=logger,
        cancellation_binder=runtime_deps.task_cancellation_binder,
        cancellation_id=task.cancellation_id,
        owner="backup_restore",
        finalizer_tracker=runtime_deps.task_finalizer_tracker,
    )
    track_operation_task(operation_tasks, operation_task)
    return task_id
