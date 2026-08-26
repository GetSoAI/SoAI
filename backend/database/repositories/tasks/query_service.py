"""SoAI - Database task query repository for listing and counting tasks [backend/database/repositories/tasks/query_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.repositories.tasks.counts import (
    build_unified_task_count,
    count_unified_tasks_visible_to_user_query,
)
from database.repositories.tasks.visibility_queries import (
    query_unified_tasks_visible_to_user_query,
    query_unified_tasks_visible_to_user_with_count_query,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseTaskQueries",)


class DatabaseTaskQueries:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._core = deps.core

    async def query_unified_tasks_visible_to_user(
        self,
        *,
        user_id: int,
        include_system: bool,
        task_type: str | None = None,
        active_only: bool = False,
        exclude_cancellation_requested: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[JSONDict]:
        return await self._core.reader.execute_read(
            query_unified_tasks_visible_to_user_query,
            user_id=user_id,
            include_system=bool(include_system),
            task_type=task_type,
            active_only=bool(active_only),
            exclude_cancellation_requested=bool(exclude_cancellation_requested),
            limit=int(limit),
            offset=int(offset),
        )

    async def query_unified_tasks_visible_to_user_with_count(
        self,
        *,
        user_id: int,
        include_system: bool,
        task_type: str | None = None,
        active_only: bool = False,
        exclude_cancellation_requested: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[JSONDict], int]:
        return await self._core.reader.execute_read(
            query_unified_tasks_visible_to_user_with_count_query,
            user_id=user_id,
            include_system=bool(include_system),
            task_type=task_type,
            active_only=bool(active_only),
            exclude_cancellation_requested=bool(exclude_cancellation_requested),
            limit=int(limit),
            offset=int(offset),
        )

    async def count_unified_tasks_visible_to_user(
        self,
        *,
        user_id: int,
        include_system: bool,
        task_type: str | None = None,
        active_only: bool = False,
        exclude_cancellation_requested: bool = False,
    ) -> int:
        return await self._core.reader.execute_read(
            count_unified_tasks_visible_to_user_query,
            user_id=user_id,
            include_system=bool(include_system),
            task_type=task_type,
            active_only=bool(active_only),
            exclude_cancellation_requested=bool(exclude_cancellation_requested),
        )

    async def count_unified_tasks(
        self,
        user_id: int | None = None,
        status: str | None = None,
        task_type: str | None = None,
        owner_type: str | None = None,
        active_only: bool = False,
        exclude_cancellation_requested: bool = False,
    ) -> int:
        return await self._core.reader.execute_read(
            build_unified_task_count,
            user_id=user_id,
            status=status,
            task_type=task_type,
            owner_type=owner_type,
            active_only=active_only,
            exclude_cancellation_requested=bool(exclude_cancellation_requested),
        )
