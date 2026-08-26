"""SoAI - Task registry visibility queries [backend/tasks/registry/query_visibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.type_catalog import TaskTypeCatalog, TaskTypeId
from tasks.registry.query_execution import rows_to_tasks
from tasks.registry.query_requests import enum_value

if TYPE_CHECKING:
    from core.tasks.protocols_query import DatabaseTaskQueriesProtocol
    from core.tasks.task import Task

__all__ = (
    "query_visible_to_user",
    "query_visible_to_user_with_count",
)


async def query_visible_to_user(
    database_task_queries: DatabaseTaskQueriesProtocol,
    task_catalog: TaskTypeCatalog,
    *,
    user_id: int,
    include_system: bool,
    task_type: TaskTypeId | None = None,
    active_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[Task]:
    return rows_to_tasks(
        task_catalog,
        await database_task_queries.query_unified_tasks_visible_to_user(
            user_id=int(user_id),
            include_system=bool(include_system),
            task_type=enum_value(task_type),
            active_only=bool(active_only),
            exclude_cancellation_requested=bool(active_only),
            limit=int(limit),
            offset=int(offset),
        ),
    )


async def query_visible_to_user_with_count(
    database_task_queries: DatabaseTaskQueriesProtocol,
    task_catalog: TaskTypeCatalog,
    *,
    user_id: int,
    include_system: bool,
    task_type: TaskTypeId | None = None,
    active_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Task], int]:
    rows, total_count = await database_task_queries.query_unified_tasks_visible_to_user_with_count(
        user_id=int(user_id),
        include_system=bool(include_system),
        task_type=enum_value(task_type),
        active_only=bool(active_only),
        exclude_cancellation_requested=bool(active_only),
        limit=int(limit),
        offset=int(offset),
    )
    return (rows_to_tasks(task_catalog, rows), int(total_count))
