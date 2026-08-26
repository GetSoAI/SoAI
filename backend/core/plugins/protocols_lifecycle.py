"""SoAI - Plugin lifecycle protocol contracts [backend/core/plugins/protocols_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Protocol

from core.concurrency.lock_types import BoundedLockResult
from core.concurrency.protocols import (
    AsyncContextManagerProtocol,
    CancellationTokenProtocol,
)
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TokenCollectionProtocol,
)

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict

__all__ = (
    "PluginLifecycleLocksProtocol",
    "PluginLifecycleProtocol",
    "SchedulableCommandProtocol",
)


class SchedulableCommandProtocol(Protocol):
    @property
    def plugin_name(self) -> str | None: ...


class PluginLifecycleLocksProtocol(Protocol):
    def __getitem__(self, key: str) -> AsyncContextManagerProtocol[None]: ...

    def get(self, key: str) -> AsyncContextManagerProtocol[None]: ...

    def bounded_lock(
        self,
        key: str,
        timeout: float,
    ) -> AsyncContextManagerProtocol[BoundedLockResult]: ...

    def is_locked(self, key: str) -> bool: ...
    def is_owned_by_current_task(self, key: str) -> bool: ...


class PluginLifecycleProtocol(Protocol):
    @property
    def cancellation_binder(self) -> TaskCancellationBinderProtocol: ...
    @property
    def finalizer_tracker(self) -> TaskFinalizerTrackerProtocol: ...
    @property
    def cancellation_coordinator(self) -> CancellationCoordinatorProtocol: ...
    @property
    def cancellation_history(self) -> CancellationHistoryProtocol: ...
    @property
    def cancellation_event_bus(self) -> CancellationEventBusProtocol: ...
    @property
    def token_collection(self) -> TokenCollectionProtocol: ...

    @property
    def disabled(self) -> bool: ...

    @property
    def shutdown_event(self) -> asyncio.Event: ...

    def require_enabled(self, service_name: str) -> None: ...
    def is_plugin_locked(self, plugin_name: str) -> bool: ...
    def is_plugin_lock_owned_by_current_task(self, plugin_name: str) -> bool: ...

    async def cancel_plugin_tasks(
        self,
        plugin_name: str,
        reason: str,
        *,
        exclude_cancellation_ids: frozenset[str] = frozenset(),
    ) -> int: ...

    async def cancel_all_plugin_tasks(
        self,
        reason: str,
        *,
        drain_timeout_sec: float,
    ) -> int: ...

    def schedule_command_task(
        self,
        *,
        service_name: str,
        command: SchedulableCommandProtocol,
        coro: Awaitable[None],
        name_template: str,
    ) -> None: ...

    def lifecycle_scope(
        self,
        *,
        service_name: str,
        task_type: str,
        plugin_name: str | None = None,
        metadata: JSONDict | None = None,
        acquire_plugin_lock: bool = False,
        user_id: int = 0,
        task_id: str | None = None,
        context: RequestContext | None = None,
    ) -> AbstractAsyncContextManager[tuple[CancellationTokenProtocol, str]]: ...

    def plugin_lock_scope(self, plugin_name: str) -> AsyncContextManagerProtocol[None]: ...

    def bounded_plugin_lock_scope(
        self,
        plugin_name: str,
        *,
        timeout_seconds: float,
    ) -> AsyncContextManagerProtocol[BoundedLockResult]: ...
