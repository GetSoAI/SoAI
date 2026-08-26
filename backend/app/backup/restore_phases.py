"""SoAI - Backup restore phase execution [backend/app/backup/restore_phases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backup.backup_timeout_settings import get_positive_float_config
from app.backup.restore_execution import restore_backup_internal
from app.backup.task_registry_reporting import update_progress_noncritical
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.logging.trace import get_logger
from core.sqlite.file_permissions import secure_sqlite_file_permissions

if TYPE_CHECKING:
    from app.backup.internal_protocols import (
        BackupRuntimeDependenciesProtocol,
        ConfigProviderProtocol,
    )
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict

__all__ = (
    "RestorePhaseResult",
    "execute_restore_phase",
    "shutdown_database_for_restore",
)

LOGGER_NAME = "SoAI.app.backup.restore_phases"


@dataclass(frozen=True, slots=True)
class RestorePhaseResult:
    result: JSONDict
    has_errors: bool


async def shutdown_database_for_restore(
    *,
    runtime_dependencies: BackupRuntimeDependenciesProtocol,
) -> None:
    await runtime_dependencies.database_core.vacuum.shutdown()
    await runtime_dependencies.database_core.reader.shutdown()
    await runtime_dependencies.database_core.writer.shutdown()


async def execute_restore_phase(
    *,
    backup_path: str,
    manifest: JSONDict,
    manifest_files: JSONDict,
    restore_destinations: dict[str, str],
    config: ConfigProviderProtocol,
    runtime_dependencies: BackupRuntimeDependenciesProtocol,
    registry: TaskRegistryProtocol,
    task_id: str,
    user_id: int,
    database_core_shutdown: bool,
) -> RestorePhaseResult | None:
    logger = get_logger(LOGGER_NAME)
    if not manifest_files:
        return None

    await update_progress_noncritical(
        registry=registry,
        task_id=task_id,
        progress_current=5,
        log=logger,
        operation="app.backup.restore_phases.restore_progress",
        message="Failed to update restore phase progress.",
        status_message="Staging restore targets",
        level="debug",
    )
    db_path = restore_destinations.get("db_path")
    restore_manifest: JSONDict = dict(manifest)
    restore_manifest["files"] = manifest_files
    restore_result = await restore_backup_internal(
        backup_path=backup_path,
        manifest=restore_manifest,
        task_id=task_id,
        user_id=user_id,
        update_task_registry=not database_core_shutdown,
        restore_destinations=restore_destinations,
        copy_timeout_seconds=get_positive_float_config(
            config,
            "DATA.BACKUP.RESTORE_COPY_TIMEOUT_SECONDS",
            1800.0,
        ),
        progress_interval_seconds=get_positive_float_config(
            config,
            "DATA.BACKUP.RESTORE_PROGRESS_INTERVAL_SECONDS",
            2.0,
        ),
        task_registry=registry,
        event_bus=runtime_dependencies.event_bus,
    )
    if database_core_shutdown and db_path:
        await run_joined_thread_call(
            secure_sqlite_file_permissions,
            db_path,
            task_name="backup-restore-database-permissions",
        )
    errors = restore_result.get("errors")
    has_errors = bool(isinstance(errors, list) and errors)
    return RestorePhaseResult(result=restore_result, has_errors=has_errors)
