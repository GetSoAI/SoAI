"""SoAI - Task registry protocol surfaces [backend/core/tasks/protocols_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol, override

from core.concurrency.protocols import AsyncContextManagerProtocol
from core.database.protocols_tasks import DatabaseTasksProtocol
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.tasks.enums import TaskStatus
from core.tasks.protocols_cancellation import (
    CancellationCoordinatorProtocol,
    CancellationHistoryProtocol,
)
from core.tasks.type_catalog import TaskTypeCatalog, TaskTypeId

if TYPE_CHECKING:
    from core.tasks.task import Task

__all__ = (
    "TaskIdentityProtocol",
    "TaskLockView",
    "TaskRegistryEvictionView",
    "TaskRegistryLifecycleView",
    "TaskRegistryProtocol",
)


class TaskLockView(Protocol):
    lock: AsyncContextManagerProtocol[None]


class TaskRegistryLifecycleView(Protocol):
    @property
    def task_catalog(self) -> TaskTypeCatalog: ...

    @property
    def database_tasks(self) -> DatabaseTasksProtocol: ...

    @property
    def event_bus(self) -> EventBusProtocol: ...

    @property
    def cancellation_coordinator(self) -> CancellationCoordinatorProtocol: ...

    @property
    def cancellation_history(self) -> CancellationHistoryProtocol: ...

    @property
    def tasks_lock(self) -> asyncio.Lock: ...

    @property
    def tasks(self) -> dict[str, Task]: ...

    @property
    def terminal_cache(self) -> dict[str, tuple[Task, float]]: ...

    @property
    def terminal_cache_ttl(self) -> float: ...

    @property
    def completion_events_lock(self) -> asyncio.Lock: ...

    @property
    def completion_events(self) -> dict[str, asyncio.Event]: ...

    @property
    def memory_cache_max_size(self) -> int: ...

    @property
    def stuck_task_timeout_ms(self) -> int: ...

    def get_task_lock(self, task_id: str) -> TaskLockView: ...

    async def drop_task_lock(self, task_id: str) -> None: ...

    async def ensure_completion_event(
        self,
        task_id: str,
        *,
        set_if_terminal: bool,
    ) -> asyncio.Event: ...

    async def release_completion_event(self, task_id: str) -> None: ...

    async def get(self, task_id: str, *, force_refresh: bool = False) -> Task | None: ...

    async def get_many(
        self,
        task_ids: tuple[str, ...],
        *,
        force_refresh: bool = False,
    ) -> list[Task]: ...

    async def attach_reply_queue(
        self,
        task_id: str,
        reply_queue: asyncio.Queue[Event],
    ) -> Task | None: ...

    def bind_reply_queue_identity(
        self,
        reply_queue: asyncio.Queue[Event],
        *,
        task_id: str,
        user_id: int,
    ) -> None: ...

    def resolve_task_identity_for_reply_queue(
        self,
        reply_queue: asyncio.Queue[Event],
    ) -> tuple[str, int] | None: ...

    async def update_task_cache(self, task: Task) -> None: ...

    def try_log_terminal_progress(self, task: Task, *, old_status: TaskStatus) -> None: ...


class TaskRegistryEvictionView(Protocol):
    @property
    def tasks(self) -> dict[str, Task]: ...

    @property
    def memory_cache_max_size(self) -> int: ...

    @property
    def completion_events_lock(self) -> asyncio.Lock: ...

    @property
    def completion_events(self) -> dict[str, asyncio.Event]: ...

    async def ensure_completion_event(
        self,
        task_id: str,
        *,
        set_if_terminal: bool,
    ) -> asyncio.Event: ...

    async def drop_task_lock(self, task_id: str) -> None: ...


class TaskRegistryProtocol(
    TaskRegistryLifecycleView,
    TaskRegistryEvictionView,
    Protocol,
):
    @property
    def shutdown_event(self) -> asyncio.Event: ...

    @property
    def cleanup_interval_ms(self) -> int: ...

    @property
    def default_ttl_ms(self) -> int: ...

    @property
    def max_concurrent_per_owner(self) -> int: ...

    @property
    def max_concurrent_by_owner_type(self) -> dict[str, int]: ...

    @override
    async def update_task_cache(self, task: Task) -> None: ...

    async def delete(self, task_id: str) -> bool: ...

    async def wait_for_completion(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
    ) -> Task | None: ...

    def prune_stale_terminal_progress(self) -> int: ...


class TaskIdentityProtocol(Protocol):
    @property
    def task_id(self) -> str: ...

    @property
    def task_type(self) -> TaskTypeId: ...

    @property
    def status(self) -> TaskStatus: ...

    @property
    def user_id(self) -> int: ...

    @property
    def owner_id(self) -> str: ...

    @property
    def owner_type(self) -> str: ...
