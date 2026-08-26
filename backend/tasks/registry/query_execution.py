"""SoAI - Task registry query execution helpers [backend/tasks/registry/query_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from core.database.task_requests import UnifiedTaskQueryRequest
from core.tasks.type_catalog import TaskTypeCatalog, TaskTypeId
from tasks.registry.conversion import task_from_row
from tasks.registry.query_requests import build_active_query_request

if TYPE_CHECKING:
    from core.database.protocols_tasks import DatabaseTasksProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = (
    "query_active_tasks",
    "query_tasks",
    "rows_to_tasks",
)


def rows_to_tasks(task_catalog: TaskTypeCatalog, rows: Iterable[JSONDict]) -> list[Task]:
    return [task_from_row(task_catalog, row) for row in rows]


async def query_tasks(
    database_tasks: DatabaseTasksProtocol,
    task_catalog: TaskTypeCatalog,
    request: UnifiedTaskQueryRequest,
) -> list[Task]:
    rows = await database_tasks.query_unified_tasks(request)
    return rows_to_tasks(task_catalog, rows)


async def query_active_tasks(
    database_tasks: DatabaseTasksProtocol,
    task_catalog: TaskTypeCatalog,
    *,
    user_id: int | None = None,
    task_type: TaskTypeId | None = None,
    owner_type: str | None = None,
    owner_id: str | None = None,
    cancellation_id: str | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> list[Task]:
    return await query_tasks(
        database_tasks,
        task_catalog,
        build_active_query_request(
            user_id=user_id,
            task_type=task_type,
            owner_type=owner_type,
            owner_id=owner_id,
            cancellation_id=cancellation_id,
            exclude_cancellation_requested=True,
            limit=limit,
            offset=offset,
        ),
    )
