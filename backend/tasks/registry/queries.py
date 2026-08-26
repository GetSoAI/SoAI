"""SoAI - Task registry query operations [backend/tasks/registry/queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TaskTypeCatalog, TaskTypeId
from tasks.registry.query_counts import (
    count_active_by_user,
    count_active_filtered,
    count_by_user,
    count_filtered,
    count_visible_to_user,
)
from tasks.registry.query_dependencies import TaskRegistryQueriesDependencies
from tasks.registry.query_execution import query_active_tasks, query_tasks
from tasks.registry.query_keyset import (
    query_active_by_type_keyset,
    query_active_cancellation_ids,
    query_active_for_cancellation_id_keyset,
)
from tasks.registry.query_requests import (
    build_active_query_request,
    build_owner_query_request,
)
from tasks.registry.query_visibility import (
    query_visible_to_user,
    query_visible_to_user_with_count,
)

if TYPE_CHECKING:
    from core.tasks.task import Task

__all__ = ("TaskRegistryQueries",)


class TaskRegistryQueries:
    def __init__(self, deps: TaskRegistryQueriesDependencies) -> None:
        self._db_tasks = deps.database_tasks
        self._db_task_queries = deps.database_task_queries
        self._task_catalog = deps.task_catalog

    @property
    def task_catalog(self) -> TaskTypeCatalog:
        return self._task_catalog

    async def query_visible_to_user(
        self,
        *,
        user_id: int,
        include_system: bool,
        task_type: TaskTypeId | None = None,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        return await query_visible_to_user(
            self._db_task_queries,
            self._task_catalog,
            user_id=user_id,
            include_system=include_system,
            task_type=task_type,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    async def query_visible_to_user_with_count(
        self,
        *,
        user_id: int,
        include_system: bool,
        task_type: TaskTypeId | None = None,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Task], int]:
        return await query_visible_to_user_with_count(
            self._db_task_queries,
            self._task_catalog,
            user_id=user_id,
            include_system=include_system,
            task_type=task_type,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    async def count_visible_to_user(
        self,
        *,
        user_id: int,
        include_system: bool,
        task_type: TaskTypeId | None = None,
        active_only: bool = False,
    ) -> int:
        return await count_visible_to_user(
            self._db_task_queries,
            user_id=int(user_id),
            include_system=bool(include_system),
            task_type=task_type,
            active_only=active_only,
        )

    async def query_by_owner(
        self,
        owner_type: str,
        owner_id: str,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        return await query_tasks(
            self._db_tasks,
            self._task_catalog,
            build_owner_query_request(
                owner_type=owner_type,
                owner_id=owner_id,
                status=status,
                limit=limit,
                offset=offset,
            ),
        )

    async def query_active(
        self,
        *,
        task_type: TaskTypeId | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Task]:
        return await query_active_tasks(
            self._db_tasks,
            self._task_catalog,
            task_type=task_type,
            limit=limit,
            offset=offset,
        )

    async def query_active_by_user(
        self,
        user_id: int,
        *,
        task_type: TaskTypeId | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Task]:
        return await query_active_tasks(
            self._db_tasks,
            self._task_catalog,
            user_id=user_id,
            task_type=task_type,
            limit=limit,
            offset=offset,
        )

    async def query_active_filtered(
        self,
        *,
        user_id: int | None = None,
        task_type: TaskTypeId | None = None,
        owner_type: str | None = None,
        owner_id: str | None = None,
        cancellation_id: str | None = None,
        exclude_cancellation_requested: bool = True,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Task]:
        active_request = build_active_query_request(
            user_id=user_id,
            limit=limit,
            offset=offset,
            task_type=task_type,
            owner_type=owner_type,
            owner_id=owner_id,
            cancellation_id=cancellation_id,
            exclude_cancellation_requested=exclude_cancellation_requested,
        )
        return await query_tasks(self._db_tasks, self._task_catalog, active_request)

    async def query_active_cancellation_ids(
        self,
        *,
        include_internal: bool,
        limit: int = 200000,
    ) -> list[str]:
        return await query_active_cancellation_ids(
            self._db_tasks,
            include_internal=include_internal,
            limit=limit,
        )

    async def query_active_for_cancellation_id_keyset(
        self,
        cancellation_id: str,
        *,
        after_created_at_ms: int = 0,
        after_task_id: str = "",
        limit: int = 1000,
    ) -> list[Task]:
        return await query_active_for_cancellation_id_keyset(
            self._db_tasks,
            self._task_catalog,
            cancellation_id,
            after_created_at_ms=after_created_at_ms,
            after_task_id=after_task_id,
            limit=limit,
        )

    async def query_active_by_type_keyset(
        self,
        task_type: TaskTypeId,
        *,
        after_created_at_ms: int = 0,
        after_task_id: str = "",
        limit: int = 1000,
    ) -> list[Task]:
        return await query_active_by_type_keyset(
            self._db_tasks,
            self._task_catalog,
            task_type,
            after_created_at_ms=after_created_at_ms,
            after_task_id=after_task_id,
            limit=limit,
        )

    async def count_by_user(
        self,
        user_id: int,
        *,
        status: TaskStatus | None = None,
        task_type: TaskTypeId | None = None,
    ) -> int:
        return await count_by_user(
            self._db_task_queries,
            user_id,
            status=status,
            task_type=task_type,
        )

    async def count_active_by_user(
        self, user_id: int, *, task_type: TaskTypeId | None = None
    ) -> int:
        return await count_active_by_user(
            self._db_task_queries,
            user_id,
            task_type=task_type,
        )

    async def count_active_filtered(
        self,
        *,
        task_type: TaskTypeId | None = None,
        owner_type: str | None = None,
    ) -> int:
        return await count_active_filtered(
            self._db_task_queries,
            task_type=task_type,
            owner_type=owner_type,
        )

    async def count_filtered(
        self,
        *,
        user_id: int | None = None,
        task_type: TaskTypeId | None = None,
        owner_type: str | None = None,
    ) -> int:
        return await count_filtered(
            self._db_task_queries,
            user_id=user_id,
            task_type=task_type,
            owner_type=owner_type,
        )
