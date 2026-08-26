"""SoAI - Task registry count query helpers [backend/tasks/registry/query_counts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.type_catalog import TaskTypeId
from tasks.registry.query_requests import enum_value

if TYPE_CHECKING:
    from core.tasks.enums import TaskStatus
    from core.tasks.protocols_query import DatabaseTaskQueriesProtocol

__all__ = (
    "count_active_by_user",
    "count_active_filtered",
    "count_by_user",
    "count_filtered",
    "count_visible_to_user",
)


async def count_visible_to_user(
    database_task_queries: DatabaseTaskQueriesProtocol,
    *,
    user_id: int,
    include_system: bool,
    task_type: TaskTypeId | None = None,
    active_only: bool = False,
) -> int:
    return await database_task_queries.count_unified_tasks_visible_to_user(
        user_id=int(user_id),
        include_system=bool(include_system),
        task_type=enum_value(task_type),
        active_only=bool(active_only),
        exclude_cancellation_requested=bool(active_only),
    )


async def count_by_user(
    database_task_queries: DatabaseTaskQueriesProtocol,
    user_id: int,
    *,
    status: TaskStatus | None = None,
    task_type: TaskTypeId | None = None,
) -> int:
    return await database_task_queries.count_unified_tasks(
        user_id=user_id,
        status=enum_value(status),
        task_type=enum_value(task_type),
    )


async def count_active_by_user(
    database_task_queries: DatabaseTaskQueriesProtocol,
    user_id: int,
    *,
    task_type: TaskTypeId | None = None,
) -> int:
    return await database_task_queries.count_unified_tasks(
        user_id=user_id,
        task_type=enum_value(task_type),
        active_only=True,
        exclude_cancellation_requested=True,
    )


async def count_active_filtered(
    database_task_queries: DatabaseTaskQueriesProtocol,
    *,
    task_type: TaskTypeId | None = None,
    owner_type: str | None = None,
) -> int:
    return await database_task_queries.count_unified_tasks(
        task_type=enum_value(task_type),
        owner_type=owner_type,
        active_only=True,
        exclude_cancellation_requested=True,
    )


async def count_filtered(
    database_task_queries: DatabaseTaskQueriesProtocol,
    *,
    user_id: int | None = None,
    task_type: TaskTypeId | None = None,
    owner_type: str | None = None,
) -> int:
    return await database_task_queries.count_unified_tasks(
        user_id=user_id,
        task_type=enum_value(task_type),
        owner_type=owner_type,
    )
