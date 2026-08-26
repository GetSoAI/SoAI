"""SoAI - Plugin concurrency and queue capacity ownership [backend/orchestrator/capacity/capacity_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

from core.concurrency.lock_registry import TTLAsyncLockRegistry, TTLAsyncLockRegistryDependencies
from core.concurrency.swappable_resource import SwappableResource
from core.errors.exceptions import StateError, ValidationError
from core.metrics.keyspace_base import (
    DIRECTOR_GAUGE_CONCURRENCY_ACTIVE,
    DIRECTOR_GAUGE_CONCURRENCY_LIMIT,
    DIRECTOR_GAUGE_CONCURRENCY_WAITERS,
)
from core.orchestrator.protocols_queue import QueueCycleType
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.validation.integers import is_strict_int
from orchestrator.capacity.concurrency_limiter import (
    PluginConcurrencyLimiter,
    PluginConcurrencySnapshot,
)
from orchestrator.capacity.dependencies import OrchestratorCapacityDependencies
from orchestrator.capacity.plugin_queue.capacity import calculate_plugin_queue_capacity
from orchestrator.capacity.plugin_queue.errors import (
    OPERATION_ORCHESTRATOR_CAPACITY_ENQUEUE_PLUGIN_TASK,
    PluginQueueFullError,
)
from orchestrator.capacity.runtime_state import CapacityRuntimeState
from orchestrator.capacity.slot_lease import PluginSlotLease
from orchestrator.queueing.inference_priority_queue import InferencePriorityQueue

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = ("OrchestratorCapacity",)


class OrchestratorCapacity:
    def __init__(self, deps: OrchestratorCapacityDependencies) -> None:
        self._state = CapacityRuntimeState(
            config=deps.config,
            metrics=deps.metrics,
            cycles=deps.cycles,
            plugin_limiters={},
            plugin_queue_resources={},
            stale_plugin_names=set(),
            plugin_queue_lock=asyncio.Lock(),
            plugin_queue_locks=TTLAsyncLockRegistry[str](TTLAsyncLockRegistryDependencies()),
        )

    def update_config(self, config: OrchestratorRuntimeConfig) -> None:
        self._state.config = config

    async def acquire_plugin_slot(self, plugin_name: str) -> PluginSlotLease:
        limiter = self._state.plugin_limiters.get(plugin_name)
        if limiter is None:
            raise StateError(
                f"Plugin capacity was not provisioned for '{plugin_name}'.",
                operation="orchestrator.capacity.acquire_plugin_slot",
            )
        await limiter.acquire()
        return PluginSlotLease(
            plugin_name,
            lambda: self._release_limiter(plugin_name, limiter),
        )

    async def ensure_plugin_capacity(
        self,
        plugin_name: str,
        plugin_limit: int,
        plugin_count: int,
    ) -> InferencePriorityQueue[Task]:
        known_plugin_names = set(self._state.plugin_limiters) | set(
            self._state.plugin_queue_resources
        )
        effective_plugin_count = max(plugin_count, len(known_plugin_names | {plugin_name}))
        await self.update_concurrency_limits(
            {plugin_name: plugin_limit},
            plugin_count=effective_plugin_count,
        )
        return self._require_queue(plugin_name)

    async def update_concurrency_limits(
        self,
        limits: dict[str, int],
        *,
        plugin_count: int,
    ) -> None:
        if not limits:
            return
        self._validate_limits(limits)
        capacities = {
            plugin_name: calculate_plugin_queue_capacity(
                config=self._state.config,
                plugin_limit=limit,
                plugin_count=max(plugin_count, 1),
            )
            for plugin_name, limit in limits.items()
        }
        async with AsyncExitStack() as stack:
            for plugin_name in sorted(limits):
                await stack.enter_async_context(self._state.plugin_queue_locks.lock(plugin_name))
            await stack.enter_async_context(self._state.plugin_queue_lock)
            planned_queues = {
                plugin_name: self._build_queue_if_missing(plugin_name, capacities[plugin_name])
                for plugin_name in limits
            }
            planned_limiters = {
                plugin_name: self._build_limiter_if_missing(plugin_name, limits[plugin_name])
                for plugin_name in limits
            }
            for plugin_name, queue in planned_queues.items():
                resource = self._state.plugin_queue_resources.get(plugin_name)
                if resource is None:
                    self._state.plugin_queue_resources[plugin_name] = SwappableResource(queue)
                else:
                    resource.current.resize(capacities[plugin_name])
            for plugin_name, limiter in planned_limiters.items():
                if plugin_name not in self._state.plugin_limiters:
                    self._state.plugin_limiters[plugin_name] = limiter
                limiter.set_limit(limits[plugin_name], publish=False)
                limiter.activate(publish=False)
            self._state.stale_plugin_names.difference_update(limits)
            for limiter in planned_limiters.values():
                limiter.publish_snapshot()

    async def get_existing_plugin_queue_binding(
        self,
        plugin_name: str,
    ) -> tuple[asyncio.Queue[Task], asyncio.Event] | None:
        async with self._state.plugin_queue_lock:
            resource = self._state.plugin_queue_resources.get(plugin_name)
            if resource is None:
                return None
            binding = resource.bind()
            return (binding.resource, binding.swap_event)

    async def enqueue_plugin_task(self, plugin_name: str, item: Task) -> None:
        async with self._state.plugin_queue_locks.lock(plugin_name):
            async with self._state.plugin_queue_lock:
                queue = self._require_queue(plugin_name)
            try:
                await self._state.cycles.open_cycle_and_enqueue_nowait(
                    item.task_id,
                    QueueCycleType.PLUGIN,
                    queue,
                    lambda: queue.put_nowait(item),
                )
            except asyncio.QueueFull as exception:
                raise PluginQueueFullError(
                    f"Plugin queue is full for plugin '{plugin_name}'.",
                    operation=OPERATION_ORCHESTRATOR_CAPACITY_ENQUEUE_PLUGIN_TASK,
                    details={
                        "plugin": plugin_name,
                        "queue_maxsize": queue.maxsize,
                        "queue_depth": queue.qsize(),
                        "task_id": item.task_id,
                    },
                    cause=exception,
                ) from exception

    async def drain_plugin_queue(self, plugin_name: str) -> list[Task]:
        drained: list[Task] = []
        async with self._state.plugin_queue_locks.lock(plugin_name):
            async with self._state.plugin_queue_lock:
                resource = self._state.plugin_queue_resources.get(plugin_name)
                if resource is None:
                    return drained
                queue = resource.current
            while True:
                try:
                    item = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return drained
                drained.append(item)
                await self._state.cycles.close_cycle(item, QueueCycleType.PLUGIN)

    async def get_queue_empty_snapshot(self, plugin_names: list[str]) -> dict[str, bool]:
        async with self._state.plugin_queue_lock:
            return {
                name: name not in self._state.plugin_queue_resources
                or self._state.plugin_queue_resources[name].current.empty()
                for name in plugin_names
            }

    async def get_queue_sizes(self, plugin_names: list[str]) -> dict[str, int]:
        async with self._state.plugin_queue_lock:
            return {
                name: (
                    self._state.plugin_queue_resources[name].current.qsize()
                    if name in self._state.plugin_queue_resources
                    else 0
                )
                for name in plugin_names
            }

    async def is_queue_empty(self, plugin_name: str) -> bool:
        return (await self.get_queue_empty_snapshot([plugin_name]))[plugin_name]

    def get_plugin_limit(self, plugin_name: str) -> int | None:
        limiter = self._state.plugin_limiters.get(plugin_name)
        return limiter.limit if limiter is not None else None

    def requires_plugin_capacity_refresh(self, plugin_name: str) -> bool:
        return (
            plugin_name not in self._state.plugin_limiters
            or plugin_name not in self._state.plugin_queue_resources
            or plugin_name in self._state.stale_plugin_names
        )

    def get_plugin_queue_unlimited_workers(self) -> int:
        value = self._state.config.plugin_queue_unlimited_workers
        return value if is_strict_int(value) and value > 0 else 8

    def get_plugin_queue_max_workers(self) -> int:
        value = self._state.config.plugin_queue_max_workers
        return value if is_strict_int(value) and value > 0 else 32

    def mark_plugin_capacity_stale(self, plugin_name: str) -> None:
        if plugin_name:
            self._state.stale_plugin_names.add(plugin_name)

    async def remove_plugin_capacity_state(self, plugin_name: str) -> None:
        async with self._state.plugin_queue_locks.lock(plugin_name):
            async with self._state.plugin_queue_lock:
                resource = self._state.plugin_queue_resources.get(plugin_name)
                if resource is not None and not resource.current.empty():
                    raise StateError(
                        f"Cannot remove non-empty plugin queue for '{plugin_name}'.",
                        operation="orchestrator.capacity.remove_plugin_capacity_state",
                        details={"plugin": plugin_name, "queue_depth": resource.current.qsize()},
                    )
                resource = self._state.plugin_queue_resources.pop(plugin_name, None)
                if resource is not None:
                    resource.swap_event.set()
                limiter = self._state.plugin_limiters.get(plugin_name)
                if limiter is not None:
                    limiter.deactivate(publish=False)
                    if limiter.active_lease_count == 0:
                        self._state.plugin_limiters.pop(plugin_name, None)
                self._state.stale_plugin_names.discard(plugin_name)
                if limiter is not None:
                    limiter.publish_snapshot()
        await self._state.plugin_queue_locks.remove(plugin_name)

    async def get_status_snapshot(self) -> JSONDict:
        return {
            name: {
                "limit": snapshot.limit,
                "active": snapshot.active,
                "queue": snapshot.queue,
            }
            for name, limiter in self._state.plugin_limiters.items()
            if (snapshot := limiter.snapshot()).accepting or snapshot.active > 0
        }

    def _build_queue_if_missing(
        self,
        plugin_name: str,
        capacity: int,
    ) -> InferencePriorityQueue[Task]:
        resource = self._state.plugin_queue_resources.get(plugin_name)
        if resource is not None:
            return resource.current
        return InferencePriorityQueue(maxsize=capacity)

    def _build_limiter_if_missing(self, plugin_name: str, limit: int) -> PluginConcurrencyLimiter:
        existing = self._state.plugin_limiters.get(plugin_name)
        if existing is not None:
            return existing
        return PluginConcurrencyLimiter(
            plugin_name,
            limit,
            lambda snapshot: self._observe_limiter(plugin_name, snapshot),
        )

    def _observe_limiter(self, plugin_name: str, snapshot: PluginConcurrencySnapshot) -> None:
        metrics = self._state.metrics
        if metrics is None:
            return
        metrics.set_gauge(*DIRECTOR_GAUGE_CONCURRENCY_LIMIT, plugin_name, value=snapshot.limit)
        metrics.set_gauge(*DIRECTOR_GAUGE_CONCURRENCY_ACTIVE, plugin_name, value=snapshot.active)
        metrics.set_gauge(*DIRECTOR_GAUGE_CONCURRENCY_WAITERS, plugin_name, value=snapshot.queue)

    def _release_limiter(self, plugin_name: str, limiter: PluginConcurrencyLimiter) -> None:
        try:
            limiter.release()
        finally:
            if (
                not limiter.accepting
                and limiter.active_lease_count == 0
                and self._state.plugin_limiters.get(plugin_name) is limiter
            ):
                self._state.plugin_limiters.pop(plugin_name)

    def _require_queue(self, plugin_name: str) -> InferencePriorityQueue[Task]:
        return self._require_resource(plugin_name).current

    def _require_resource(
        self,
        plugin_name: str,
    ) -> SwappableResource[InferencePriorityQueue[Task]]:
        resource = self._state.plugin_queue_resources.get(plugin_name)
        if resource is None:
            raise StateError(
                f"Plugin queue was not provisioned for '{plugin_name}'.",
                operation="orchestrator.capacity.plugin_queue_registry",
            )
        return resource

    @staticmethod
    def _validate_limits(limits: dict[str, int]) -> None:
        for plugin_name, limit in limits.items():
            if not plugin_name:
                raise ValidationError("Plugin name must be provided for capacity configuration.")
            if not is_strict_int(limit) or limit < 0:
                raise ValidationError(
                    f"Concurrency limit for plugin '{plugin_name}' must be an integer greater than or equal to zero.",
                )
