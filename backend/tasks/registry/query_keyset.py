"""SoAI - Task registry keyset and active ID queries [backend/tasks/registry/query_keyset.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.type_catalog import TaskTypeCatalog, TaskTypeId
from tasks.registry.query_execution import rows_to_tasks

if TYPE_CHECKING:
    from core.database.protocols_tasks import DatabaseTasksProtocol
    from core.tasks.task import Task

__all__ = (
    "query_active_by_type_keyset",
    "query_active_cancellation_ids",
    "query_active_for_cancellation_id_keyset",
)


async def query_active_cancellation_ids(
    database_tasks: DatabaseTasksProtocol,
    *,
    include_internal: bool,
    limit: int = 200000,
) -> list[str]:
    return await database_tasks.query_active_cancellation_ids(
        include_internal=bool(include_internal),
        limit=int(limit),
    )


async def query_active_for_cancellation_id_keyset(
    database_tasks: DatabaseTasksProtocol,
    task_catalog: TaskTypeCatalog,
    cancellation_id: str,
    *,
    after_created_at_ms: int = 0,
    after_task_id: str = "",
    limit: int = 1000,
) -> list[Task]:
    return rows_to_tasks(
        task_catalog,
        await database_tasks.query_active_tasks_for_cancellation_id(
            cancellation_id,
            after_created_at_ms=int(after_created_at_ms),
            after_task_id=after_task_id,
            limit=int(limit),
        ),
    )


async def query_active_by_type_keyset(
    database_tasks: DatabaseTasksProtocol,
    task_catalog: TaskTypeCatalog,
    task_type: TaskTypeId,
    *,
    after_created_at_ms: int = 0,
    after_task_id: str = "",
    limit: int = 1000,
) -> list[Task]:
    return rows_to_tasks(
        task_catalog,
        await database_tasks.query_active_tasks_by_type(
            task_type,
            after_created_at_ms=int(after_created_at_ms),
            after_task_id=after_task_id,
            limit=int(limit),
        ),
    )
