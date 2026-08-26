"""SoAI - Plugin lifecycle task management and cancellation tracking [backend/plugins/lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from plugins.lifecycle_active_cancellation import register_active_cancellation
from plugins.lifecycle_dependencies import (
    ActiveCancellationRecord,
    PluginLifecycleDependencies,
)
from plugins.lifecycle_scope_exit import finalize_scope_exit_if_needed
from plugins.lifecycle_shutdown_cancellation import (
    cancel_and_drain_registered_plugin_tasks,
    cancel_registered_plugin_tasks,
)
from plugins.lifecycle_task_finalization import finalize_task_on_error
from plugins.lifecycle_task_initialization import initialize_lifecycle_task

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable

    from core.concurrency.lock_types import BoundedLockResult
    from core.concurrency.protocols import AsyncContextManagerProtocol, CancellationTokenProtocol
    from core.plugins.protocols_lifecycle import SchedulableCommandProtocol
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import (
        CancellationCoordinatorProtocol,
        CancellationEventBusProtocol,
        CancellationHistoryProtocol,
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TokenCollectionProtocol,
    )
    from core.types.json import JSONDict

__all__ = ("PluginLifecycle",)

LOGGER_NAME = "SoAI.plugins.lifecycle"
_LIFECYCLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    asyncio.CancelledError,
    *HANDLED_RUNTIME_EXCEPTIONS,
)


class PluginLifecycle:
    def __init__(self, deps: PluginLifecycleDependencies) -> None:
        self._deps = deps
        self._active_cancellation_tasks: dict[str, dict[str, ActiveCancellationRecord]] = {}
        self._active_cancellation_lock = asyncio.Lock()

    @property
    def disabled(self) -> bool:
        return bool(self._deps.lifecycle.disabled)

    @property
    def shutdown_event(self) -> asyncio.Event:
        return self._deps.lifecycle.shutdown_event

    @property
    def cancellation_binder(self) -> TaskCancellationBinderProtocol:
        return self._deps.cancellation_binder

    @property
    def finalizer_tracker(self) -> TaskFinalizerTrackerProtocol:
        return self._deps.lifecycle.finalizer_tracker

    @property
    def cancellation_coordinator(self) -> CancellationCoordinatorProtocol:
        return self._deps.cancellation_coordinator

    @property
    def cancellation_history(self) -> CancellationHistoryProtocol:
        return self._deps.cancellation_history

    @property
    def cancellation_event_bus(self) -> CancellationEventBusProtocol:
        return self._deps.cancellation_event_bus

    @property
    def token_collection(self) -> TokenCollectionProtocol:
        return self._deps.token_collection

    def require_enabled(self, service_name: str) -> None:
        self._deps.lifecycle.require_enabled(service_name)

    def is_plugin_locked(self, plugin_name: str) -> bool:
        return self._deps.locks.is_locked(plugin_name)

    def is_plugin_lock_owned_by_current_task(self, plugin_name: str) -> bool:
        return self._deps.locks.is_owned_by_current_task(plugin_name)

    @staticmethod
    def format_task_name(template: str, command: SchedulableCommandProtocol) -> str:
        plugin_name = command.plugin_name or "system"
        return template.format(command=command, plugin=plugin_name, plugin_name=plugin_name)

    def schedule_command_task(
        self,
        *,
        service_name: str,
        command: SchedulableCommandProtocol,
        coro: Awaitable[None],
        name_template: str,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        self._deps.lifecycle.require_enabled(service_name)
        task_name = self.format_task_name(name_template, command)
        _ = self._deps.create_managed_task(
            coro,
            logger=logger,
            name=task_name,
        )

    async def _register_active_cancellation(
        self,
        *,
        service_name: str,
        cancellation_id: str,
        task: asyncio.Task[None],
        task_type: str,
        plugin_name: str | None = None,
        metadata: JSONDict | None = None,
    ) -> tuple[CancellationTokenProtocol, str]:
        return await register_active_cancellation(
            self._deps,
            self._active_cancellation_lock,
            self._active_cancellation_tasks,
            service_name=service_name,
            cancellation_id=cancellation_id,
            task=task,
            task_type=task_type,
            plugin_name=plugin_name,
            metadata=metadata,
        )

    async def cancel_plugin_tasks(
        self,
        plugin_name: str,
        reason: str,
        *,
        exclude_cancellation_ids: frozenset[str] = frozenset(),
    ) -> int:
        return await cancel_registered_plugin_tasks(
            self._deps,
            self._active_cancellation_lock,
            self._active_cancellation_tasks,
            plugin_name=plugin_name,
            reason=reason,
            exclude_cancellation_ids=exclude_cancellation_ids,
        )

    async def cancel_all_plugin_tasks(
        self,
        reason: str,
        *,
        drain_timeout_sec: float,
    ) -> int:
        return await cancel_and_drain_registered_plugin_tasks(
            self._deps,
            self._active_cancellation_lock,
            self._active_cancellation_tasks,
            reason=reason,
            drain_timeout_sec=drain_timeout_sec,
        )

    @asynccontextmanager
    async def plugin_lock_scope(self, plugin_name: str) -> AsyncGenerator[None]:
        async with self._deps.locks[plugin_name]:
            yield

    def bounded_plugin_lock_scope(
        self,
        plugin_name: str,
        *,
        timeout_seconds: float,
    ) -> AsyncContextManagerProtocol[BoundedLockResult]:
        return self._deps.locks.bounded_lock(plugin_name, timeout_seconds)

    @asynccontextmanager
    async def lifecycle_scope(
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
    ) -> AsyncGenerator[tuple[CancellationTokenProtocol, str]]:
        current_task = asyncio.current_task()
        if current_task is None:
            raise StateError("Lifecycle scope requires an active asyncio task.")
        registry = self._deps.task_registry
        unified_task_id: str | None = None
        token: CancellationTokenProtocol | None = None
        mutation_fencing_token = context.mutation_fencing_token if context is not None else None
        try:
            initialized_task = await initialize_lifecycle_task(
                self._deps,
                registry,
                task_type=task_type,
                plugin_name=plugin_name,
                metadata=metadata,
                user_id=user_id,
                task_id=task_id,
                context=context,
            )
            unified_task_id = initialized_task.task_id
            await self._deps.task_update_status(registry, unified_task_id, TaskStatus.WORKING)
            token, _task_key = await self._register_active_cancellation(
                service_name=service_name,
                cancellation_id=initialized_task.cancellation_id,
                task=current_task,
                task_type=task_type,
                plugin_name=plugin_name,
                metadata=metadata,
            )
        except asyncio.CancelledError as cancel_error:
            await finalize_task_on_error(
                self._deps,
                registry,
                task_id=unified_task_id,
                exception=cancel_error,
                mutation_fencing_token=mutation_fencing_token,
            )
            raise
        except RECOVERABLE_EXCEPTIONS as exception:
            await finalize_task_on_error(
                self._deps,
                registry,
                task_id=unified_task_id,
                exception=exception,
                mutation_fencing_token=mutation_fencing_token,
            )
            raise StateError(f"Failed to create unified task for {task_type}.") from exception
        if token is None:
            raise StateError(f"Failed to create lifecycle token for {task_type}.")
        try:
            if acquire_plugin_lock and plugin_name:
                async with self._deps.locks[plugin_name]:
                    yield (token, unified_task_id)
            else:
                yield (token, unified_task_id)
        except _LIFECYCLE_EXCEPTIONS as exception:
            await finalize_task_on_error(
                self._deps,
                registry,
                task_id=unified_task_id,
                exception=exception,
                mutation_fencing_token=mutation_fencing_token,
            )
            raise
        await finalize_scope_exit_if_needed(
            self._deps,
            unified_task_id=unified_task_id,
            task_type=task_type,
            plugin_name=plugin_name,
            mutation_fencing_token=mutation_fencing_token,
        )
