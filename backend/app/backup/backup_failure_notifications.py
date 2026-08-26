"""SoAI - Backup failure notification helpers [backend/app/backup/backup_failure_notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import InsufficientDiskSpaceError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.notifications.system_admin_alerts import (
    create_backup_failure_admin_alert,
    create_low_disk_space_admin_alert,
)

if TYPE_CHECKING:
    from app.backup.internal_protocols import BackupRuntimeDependenciesProtocol
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "notify_backup_failure_noncritical",
    "notify_backup_low_disk_noncritical",
)

OPERATION_BACKUP_FAILURE_NOTIFICATION = "app.backup.failure_notifications.backup_failure"
OPERATION_LOW_DISK_NOTIFICATION = "app.backup.failure_notifications.low_disk"


async def notify_backup_failure_noncritical(
    *,
    runtime_dependencies: BackupRuntimeDependenciesProtocol,
    operation_label: str,
    task_id: str,
    log: LoggerProtocol,
) -> None:
    try:
        await create_backup_failure_admin_alert(
            runtime_dependencies.database_notifications,
            operation_label=operation_label,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            log,
            exception,
            message="Failed to create backup failure notification.",
            operation=OPERATION_BACKUP_FAILURE_NOTIFICATION,
            details={"task_id": task_id, "operation_label": operation_label},
            level="warning",
        )


async def notify_backup_low_disk_noncritical(
    *,
    runtime_dependencies: BackupRuntimeDependenciesProtocol,
    exception: InsufficientDiskSpaceError,
    fallback_operation_label: str,
    task_id: str,
    log: LoggerProtocol,
) -> None:
    try:
        await create_low_disk_space_admin_alert(
            runtime_dependencies.database_notifications,
            exception=exception,
            fallback_operation_label=fallback_operation_label,
        )
    except RECOVERABLE_EXCEPTIONS as notify_exception:
        log_exception(
            log,
            notify_exception,
            message="Failed to create low disk space notification.",
            operation=OPERATION_LOW_DISK_NOTIFICATION,
            details={"task_id": task_id, "operation_label": fallback_operation_label},
            level="warning",
        )
