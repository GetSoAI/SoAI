"""SoAI - Protocol interfaces for task registry and lifecycle [backend/core/tasks/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING, AsyncContextManager, Protocol

from core.concurrency.protocols import CancellationTokenProtocol
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol
from core.runtime.request_context import RequestContext
from core.tasks.cancellation_types import (
    AddTokenResult,
    CancelAllResult,
    ClearScopeResult,
    HistorySnapshot,
    RecordCancellationResult,
    RemoveTokenResult,
    SweepResult,
)
from core.tasks.protocols_cancellation import (
    CancellationCoordinatorProtocol,
    CancellationHistoryProtocol,
)
from core.tasks.protocols_registry import (
    TaskIdentityProtocol,
    TaskLockView,
    TaskRegistryEvictionView,
    TaskRegistryLifecycleView,
    TaskRegistryProtocol,
)
from core.tasks.type_catalog import TaskTypeId

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "AddTokenResult",
    "CancelAllResult",
    "CancelTaskCallable",
    "CancellationCoordinatorProtocol",
    "CancellationEventBusProtocol",
    "CancellationHistoryProtocol",
    "CancellationTokenProtocol",
    "CancellationTokenScopeCallable",
    "ClearScopeResult",
    "CommandWithContextProtocol",
    "Event",
    "HistorySnapshot",
    "LoggerProtocol",
    "RecordCancellationResult",
    "RecoveryQueuePurgeProtocol",
    "RemoveTokenResult",
    "RequestContext",
    "SpawnTrackedBackgroundTaskCallable",
    "SpawnTrackedTaskCallable",
    "SweepResult",
    "TaskIdentityProtocol",
    "TaskLockView",
    "TaskRegistryEvictionView",
    "TaskRegistryLifecycleView",
    "TaskRegistryProtocol",
    "TaskTypeId",
    "TaskTypeRoutingServiceProtocol",
    "TokenCollectionProtocol",
)


class CommandWithContextProtocol(Protocol):
    @property
    def context(self) -> RequestContext | None: ...


class TaskTypeRoutingServiceProtocol(Protocol):
    def get_task_type_for_command(self, command_class: type[Event]) -> TaskTypeId: ...


class TokenCollectionProtocol(Protocol):
    async def add_token(
        self,
        cancellation_id: str,
        token: CancellationTokenProtocol,
    ) -> AddTokenResult: ...

    async def remove_token(
        self,
        cancellation_id: str,
        token: CancellationTokenProtocol,
    ) -> RemoveTokenResult: ...

    async def get_tokens_for_scope(
        self,
        cancellation_id: str,
    ) -> set[CancellationTokenProtocol]: ...

    async def get_all_scope_ids(self, *, include_internal: bool) -> list[str]: ...

    async def has_active_tokens(self, *, include_internal: bool) -> bool: ...

    async def sweep_cancelled(self) -> SweepResult: ...

    async def clear_scope(self, cancellation_id: str) -> ClearScopeResult: ...

    async def clear_all(self) -> None: ...


class CancellationEventBusProtocol(Protocol):
    async def subscribe(
        self,
    ) -> tuple[asyncio.Queue[JSONDict], Callable[[], Awaitable[None]]]: ...

    async def publish_event(self, event_type: str, cancellation_id: str | None = None) -> None: ...

    def update_queue_size(self, size: int) -> None: ...

    def get_queue_size(self) -> int: ...


class TaskCancellationBinderProtocol(Protocol):
    async def bind_task[TaskResult](
        self,
        cancellation_id: str,
        task: asyncio.Task[TaskResult],
        *,
        owner: str,
        metadata: dict[str, JSONValue] | None = None,
    ) -> CancellationTokenProtocol: ...


class TaskFinalizerTrackerProtocol(Protocol):
    def track_finalizer(self, task: asyncio.Task[None]) -> None: ...

    async def await_all_finalizers(
        self,
        *,
        timeout: float = 5.0,
        logger: LoggerProtocol | None = None,
    ) -> bool: ...


class SpawnTrackedTaskCallable(Protocol):
    def __call__[TaskResult](
        self,
        coro: Coroutine[None, None, TaskResult] | Awaitable[TaskResult],
        *,
        name: str | None = None,
        logger: LoggerProtocol | None = None,
        done_callback: Callable[[asyncio.Task[TaskResult]], None] | None = None,
        cancellation_binder: TaskCancellationBinderProtocol | None = None,
        cancellation_id: str | None = None,
        owner: str = "",
        metadata: dict[str, JSONValue] | None = None,
        finalizer_tracker: TaskFinalizerTrackerProtocol | None = None,
        owner_observes_result: bool = False,
    ) -> asyncio.Task[TaskResult]: ...


class SpawnTrackedBackgroundTaskCallable(Protocol):
    async def __call__(
        self,
        *,
        coro: Coroutine[None, None, None],
        owner: str,
        metadata: dict[str, JSONValue] | None = None,
        cancellation_id: str | None = None,
        name: str | None = None,
    ) -> asyncio.Task[None]: ...


class RecoveryQueuePurgeProtocol(Protocol):
    async def __call__(
        self,
        *,
        plugin_name: str,
        reason: str,
    ) -> None: ...


class CancelTaskCallable(Protocol):
    async def __call__(
        self,
        task: asyncio.Task[None] | None,
        *,
        logger: LoggerProtocol | None = None,
        label: str = "task",
    ) -> None: ...


class CancellationTokenScopeCallable(Protocol):
    def __call__(
        self,
        token_collection: TokenCollectionProtocol,
        cancellation_history: CancellationHistoryProtocol,
        cancellation_event_bus: CancellationEventBusProtocol,
        *,
        cancellation_id: str,
        owner: str,
        metadata: dict[str, JSONValue] | None = None,
        on_cancel: Callable[[str], None] | None = None,
        logger: LoggerProtocol | None = None,
    ) -> AsyncContextManager[CancellationTokenProtocol]: ...
