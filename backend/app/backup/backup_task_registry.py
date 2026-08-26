"""SoAI - Backup task registry helpers [backend/app/backup/backup_task_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backup.task_registry_reporting import update_status_noncritical
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import build_soai_id, create_system_id
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.type_catalog import TaskTypeId

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "BackupTaskRecord",
    "create_task_record",
    "track_operation_task",
)

LOGGER_NAME = "SoAI.app.backup.backup_task_registry"


@dataclass(frozen=True, slots=True)
class BackupTaskRecord:
    task_id: str
    cancellation_id: str


async def create_task_record(
    *,
    task_registry: TaskRegistryProtocol,
    task_type: TaskTypeId,
    user_id: int,
    owner_id: str,
    metadata: dict[str, JSONValue],
    status_message: str,
) -> BackupTaskRecord:
    logger = get_logger(LOGGER_NAME)
    normalized_user_id = 0 if isinstance(user_id, bool) else int(user_id)
    if normalized_user_id > 0:
        cancellation_id = build_soai_id(("task", "backup", task_type, uuid.uuid4().hex[:12]))
    else:
        cancellation_id = create_system_id(
            subsystem="backup",
            owner=task_type,
            include_random_suffix=True,
        )
    task = await create(
        task_registry,
        task_type=task_type,
        user_id=normalized_user_id,
        owner_id=owner_id,
        owner_type="system",
        cancellation_id=cancellation_id,
        progress_total=100,
        metadata=metadata,
    )
    await update_status_noncritical(
        registry=task_registry,
        task_id=task.task_id,
        new_status=TaskStatus.WORKING,
        log=logger,
        operation="app.backup.backup_task_registry.create_task_record",
        message="Failed to update backup task record startup status.",
        status_message=status_message,
        level="debug",
    )
    return BackupTaskRecord(task_id=task.task_id, cancellation_id=task.cancellation_id)


def track_operation_task(
    operation_tasks: set[asyncio.Task[None]],
    operation_task: asyncio.Task[None],
) -> None:
    operation_tasks.add(operation_task)
    operation_task.add_done_callback(operation_tasks.discard)
