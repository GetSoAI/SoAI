"""SoAI - Task registry query protocol contracts [backend/core/tasks/protocols_query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TaskTypeCatalog, TaskTypeId

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = ("DatabaseTaskQueriesProtocol", "TaskRegistryQueryView")


class DatabaseTaskQueriesProtocol(Protocol):
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
    ) -> list[JSONDict]: ...

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
    ) -> tuple[list[JSONDict], int]: ...

    async def count_unified_tasks_visible_to_user(
        self,
        *,
        user_id: int,
        include_system: bool,
        task_type: str | None = None,
        active_only: bool = False,
        exclude_cancellation_requested: bool = False,
    ) -> int: ...

    async def count_unified_tasks(
        self,
        user_id: int | None = None,
        status: str | None = None,
        task_type: str | None = None,
        owner_type: str | None = None,
        active_only: bool = False,
        exclude_cancellation_requested: bool = False,
    ) -> int: ...


class TaskRegistryQueryView(Protocol):
    @property
    def task_catalog(self) -> TaskTypeCatalog: ...

    async def query_visible_to_user(
        self,
        *,
        user_id: int,
        include_system: bool,
        task_type: TaskTypeId | None = None,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]: ...

    async def query_visible_to_user_with_count(
        self,
        *,
        user_id: int,
        include_system: bool,
        task_type: TaskTypeId | None = None,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Task], int]: ...

    async def count_visible_to_user(
        self,
        *,
        user_id: int,
        include_system: bool,
        task_type: TaskTypeId | None = None,
        active_only: bool = False,
    ) -> int: ...

    async def query_by_owner(
        self,
        owner_type: str,
        owner_id: str,
        *,
        status: TaskStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]: ...

    async def query_active(
        self,
        *,
        task_type: TaskTypeId | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Task]: ...

    async def query_active_by_user(
        self,
        user_id: int,
        *,
        task_type: TaskTypeId | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Task]: ...

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
    ) -> list[Task]: ...

    async def query_active_cancellation_ids(
        self,
        *,
        include_internal: bool,
        limit: int = 200000,
    ) -> list[str]: ...

    async def query_active_for_cancellation_id_keyset(
        self,
        cancellation_id: str,
        *,
        after_created_at_ms: int = 0,
        after_task_id: str = "",
        limit: int = 1000,
    ) -> list[Task]: ...

    async def query_active_by_type_keyset(
        self,
        task_type: TaskTypeId,
        *,
        after_created_at_ms: int = 0,
        after_task_id: str = "",
        limit: int = 1000,
    ) -> list[Task]: ...

    async def count_by_user(
        self,
        user_id: int,
        *,
        status: TaskStatus | None = None,
        task_type: TaskTypeId | None = None,
    ) -> int: ...

    async def count_active_by_user(
        self,
        user_id: int,
        *,
        task_type: TaskTypeId | None = None,
    ) -> int: ...

    async def count_active_filtered(
        self,
        *,
        task_type: TaskTypeId | None = None,
        owner_type: str | None = None,
    ) -> int: ...

    async def count_filtered(
        self,
        *,
        user_id: int | None = None,
        task_type: TaskTypeId | None = None,
        owner_type: str | None = None,
    ) -> int: ...
