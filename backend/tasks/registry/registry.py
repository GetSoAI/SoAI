"""SoAI - Task lifecycle registry with caching and cleanup automation [backend/tasks/registry/registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.events.types_base import Event
from core.tasks.enums import TaskStatus
from core.tasks.identifiers import normalize_optional_task_id, require_task_id
from core.tasks.task import Task
from core.validation.requirements import require_non_negative_int, require_positive_int
from tasks.registry.cache_operations import clear_task_from_caches, update_task_cache
from tasks.registry.completion_waiting import wait_for_task_completion
from tasks.registry.dependencies import TaskRegistryDependencies
from tasks.registry.lifecycle import (
    initialize_task_registry_subscriptions,
    start_task_registry_cleanup_loop,
)
from tasks.registry.locks import TaskLock
from tasks.registry.owner_limits import normalize_owner_type_limits
from tasks.registry.reply_queue_attachment import attach_reply_queue_to_task
from tasks.registry.reply_queue_identity import ReplyQueueIdentityBindings
from tasks.registry.shutdown_operations import shutdown_registry
from tasks.registry.task_completion_events import TaskCompletionEvents
from tasks.registry.task_retrieval import (
    retrieve_cached_task,
    retrieve_task,
    retrieve_tasks,
)
from tasks.registry.terminal_progress import (
    TerminalProgressState,
    prune_stale_terminal_progress,
    try_log_terminal_progress,
)

if TYPE_CHECKING:
    from core.database.protocols_tasks import DatabaseTasksProtocol
    from core.events.protocols import EventBusProtocol
    from core.tasks.protocols import (
        CancellationCoordinatorProtocol,
        CancellationHistoryProtocol,
        TaskLockView,
    )

__all__ = ("TaskRegistry",)


class TaskRegistry:
    def __init__(self, deps: TaskRegistryDependencies) -> None:
        self.database_tasks: DatabaseTasksProtocol = deps.database_tasks
        self.event_bus: EventBusProtocol = deps.event_bus
        self.cancellation_coordinator: CancellationCoordinatorProtocol = (
            deps.cancellation_coordinator
        )
        self.cancellation_history: CancellationHistoryProtocol = deps.cancellation_history
        self._cancellation_binder = deps.cancellation_binder
        self._finalizer_tracker = deps.finalizer_tracker
        self.task_catalog = deps.task_catalog
        self.max_concurrent_per_owner = require_positive_int(
            deps.config.max_concurrent_per_owner,
            name="max_concurrent_per_owner",
        )
        self.max_concurrent_by_owner_type = normalize_owner_type_limits(
            deps.config.max_concurrent_by_owner_type,
        )
        self.default_ttl_ms = deps.config.default_ttl_ms
        self.cleanup_interval_ms = deps.config.cleanup_interval_ms
        self.memory_cache_max_size = deps.config.memory_cache_max_size
        self.stuck_task_timeout_ms = require_non_negative_int(
            deps.config.stuck_task_timeout_ms,
            error_message="stuck_task_timeout_ms must be a non-negative integer",
        )
        self.tasks: dict[str, Task] = {}
        self.tasks_lock = asyncio.Lock()
        self.terminal_cache: dict[str, tuple[Task, float]] = {}
        self.terminal_cache_ttl = (
            float(
                require_non_negative_int(
                    deps.config.terminal_grace_ms,
                    error_message="terminal_grace_ms must be a non-negative integer",
                ),
            )
            / 1000.0
        )
        self._terminal_progress_states: dict[str, TerminalProgressState] = {}
        self._completion_events = TaskCompletionEvents(
            max_size=deps.config.memory_cache_max_size * 2,
        )
        self.completion_events_lock = self._completion_events.lock
        self.completion_events = self._completion_events.events
        self._task_locks = TTLAsyncLockRegistry[str](
            TTLAsyncLockRegistryDependencies(
                ttl_seconds=7200.0,
                max_size=deps.config.memory_cache_max_size * 2,
                cleanup_interval_seconds=300.0,
            ),
        )
        self._reply_queue_identities = ReplyQueueIdentityBindings()
        self._cleanup_task: asyncio.Task[None] | None = None
        self.shutdown_event = asyncio.Event()
        self._subscriptions_initialized = False

    def initialize_subscriptions(self) -> None:
        if not self._subscriptions_initialized:
            self._subscriptions_initialized = True
            initialize_task_registry_subscriptions(self)

    def get_task_lock(self, task_id: str) -> TaskLockView:
        normalized_task_id = require_task_id(task_id, error_message="task_id is required.")
        return TaskLock(lambda: self._task_locks.lock(normalized_task_id))

    async def drop_task_lock(self, task_id: str) -> None:
        normalized_task_id = normalize_optional_task_id(task_id)
        if normalized_task_id is None:
            return
        await self._task_locks.remove(normalized_task_id)

    async def ensure_completion_event(
        self,
        task_id: str,
        *,
        set_if_terminal: bool,
    ) -> asyncio.Event:
        normalized_task_id = require_task_id(task_id, error_message="task_id is required.")
        return await self._completion_events.ensure(
            normalized_task_id,
            set_if_terminal=set_if_terminal,
        )

    async def release_completion_event(self, task_id: str) -> None:
        normalized_task_id = normalize_optional_task_id(task_id)
        if normalized_task_id is None:
            return
        await self._completion_events.release(normalized_task_id)

    async def update_task_cache(self, task: Task) -> None:
        await update_task_cache(
            self,
            task,
            lambda tid, terminal: self.ensure_completion_event(tid, set_if_terminal=terminal),
        )

    def try_log_terminal_progress(self, task: Task, *, old_status: TaskStatus) -> None:
        try_log_terminal_progress(
            task,
            old_status=old_status,
            states=self._terminal_progress_states,
        )

    def prune_stale_terminal_progress(self) -> int:
        return prune_stale_terminal_progress(
            self._terminal_progress_states,
            known_task_ids=set(self.tasks) | set(self.terminal_cache),
        )

    def bind_reply_queue_identity(
        self,
        reply_queue: asyncio.Queue[Event],
        *,
        task_id: str,
        user_id: int,
    ) -> None:
        self._reply_queue_identities.bind(
            reply_queue,
            task_id=task_id,
            user_id=user_id,
        )

    def resolve_task_identity_for_reply_queue(
        self,
        reply_queue: asyncio.Queue[Event],
    ) -> tuple[str, int] | None:
        identity = self._reply_queue_identities.resolve(reply_queue)
        if identity is None:
            return None
        task_id, user_id = identity
        if not task_id:
            return None
        return (task_id, user_id)

    async def attach_reply_queue(
        self,
        task_id: str,
        reply_queue: asyncio.Queue[Event],
    ) -> Task | None:
        return await attach_reply_queue_to_task(
            self,
            task_id,
            reply_queue,
            get_task_fn=self.get,
            get_task_lock_fn=self.get_task_lock,
            bind_identity_fn=lambda bound_queue, tid, uid: self.bind_reply_queue_identity(
                bound_queue,
                task_id=tid,
                user_id=uid,
            ),
        )

    async def get(self, task_id: str, *, force_refresh: bool = False) -> Task | None:
        return await retrieve_task(
            self,
            self.database_tasks,
            task_id,
            force_refresh=force_refresh,
            ensure_completion_event_fn=lambda tid, terminal: self.ensure_completion_event(
                tid,
                set_if_terminal=terminal,
            ),
        )

    async def get_many(
        self,
        task_ids: tuple[str, ...],
        *,
        force_refresh: bool = False,
    ) -> list[Task]:
        return await retrieve_tasks(
            self,
            self.database_tasks,
            task_ids,
            force_refresh=force_refresh,
            ensure_completion_event_fn=lambda tid, terminal: self.ensure_completion_event(
                tid,
                set_if_terminal=terminal,
            ),
        )

    async def get_cached(self, task_id: str) -> Task | None:
        normalized_task_id = normalize_optional_task_id(task_id)
        if normalized_task_id is None:
            return None
        return await retrieve_cached_task(self, normalized_task_id)

    async def wait_for_completion(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
    ) -> Task | None:
        return await wait_for_task_completion(
            task_id,
            timeout=timeout,
            get_task_fn=self.get,
            ensure_completion_event_fn=lambda tid, terminal: self.ensure_completion_event(
                tid,
                set_if_terminal=terminal,
            ),
            release_completion_event_fn=self.release_completion_event,
        )

    async def clear_task_from_caches(self, task_id: str) -> None:
        await clear_task_from_caches(self, task_id)

    async def delete(self, task_id: str) -> bool:
        db_success = await self.database_tasks.delete_unified_task(task_id)
        if not db_success:
            return False
        await clear_task_from_caches(self, task_id)
        await self.drop_task_lock(task_id)
        return True

    def start_cleanup_loop(self) -> None:
        self._cleanup_task = start_task_registry_cleanup_loop(
            self,
            current_cleanup_task=self._cleanup_task,
            cancellation_binder=self._cancellation_binder,
            finalizer_tracker=self._finalizer_tracker,
        )

    async def shutdown(self) -> None:
        self._cleanup_task = await shutdown_registry(self, self.shutdown_event, self._cleanup_task)
