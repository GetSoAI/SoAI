"""SoAI - Dynamic queue capacity limiter for orchestrator task ingress [backend/orchestrator/queueing/priority/queue_capacity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.concurrency.swappable_resource import SwappableResource

__all__ = (
    "QueueCapacityLimiter",
    "QueueCapacityPermit",
)


class QueueCapacityLimiter:
    def __init__(self, *, limit: int) -> None:
        normalized_limit = int(limit)
        self._limit = normalized_limit
        self._enabled = normalized_limit > 0
        self._held = 0
        self._inflight = 0
        self._waiters = 0
        initial_available = (
            max(0, normalized_limit - (self._held + self._inflight)) if self._enabled else 0
        )
        self._resource: SwappableResource[asyncio.Semaphore] = SwappableResource(
            asyncio.Semaphore(initial_available),
        )

    @property
    def limit(self) -> int:
        return int(self._limit)

    @property
    def enabled(self) -> bool:
        return bool(self._enabled)

    @property
    def held(self) -> int:
        return int(self._held)

    def update_limit(self, limit: int) -> None:
        normalized_limit = int(limit)
        previous_limit = self._limit
        previous_enabled = self._enabled
        self._limit = normalized_limit
        self._enabled = normalized_limit > 0
        if previous_limit == normalized_limit and previous_enabled == self._enabled:
            return
        old_semaphore = self._resource.current
        waiter_count = self._waiters
        available = max(0, normalized_limit - (self._held + self._inflight)) if self._enabled else 0
        self._resource.swap(asyncio.Semaphore(available))
        if waiter_count > 0:
            for _ in range(waiter_count):
                old_semaphore.release()

    async def acquire_enqueue_permission(
        self,
        *,
        timeout_seconds: float,
    ) -> QueueCapacityPermit | None:
        if not self._enabled or self._limit <= 0:
            return None
        timeout_value = max(0.0, float(timeout_seconds))
        while True:
            binding = self._resource.bind()
            self._waiters += 1
            try:
                await asyncio.wait_for(binding.resource.acquire(), timeout=timeout_value)
            finally:
                self._waiters = max(0, self._waiters - 1)
            if not self._enabled or self._limit <= 0:
                binding.resource.release()
                return None
            if not self._resource.is_current_generation(binding.generation):
                binding.resource.release()
                continue
            self._inflight += 1
            return QueueCapacityPermit(
                limiter=self,
                semaphore=binding.resource,
                generation=binding.generation,
            )

    def commit_enqueued_from_permit(self, permit: QueueCapacityPermit) -> None:
        if permit.finalized:
            return
        permit.finalized = True
        self._inflight = max(0, self._inflight - 1)
        self._held += 1

    def rollback_failed_enqueue_from_permit(self, permit: QueueCapacityPermit) -> None:
        if permit.finalized:
            return
        permit.finalized = True
        self._inflight = max(0, self._inflight - 1)
        permit.semaphore.release()
        if self._enabled and self._limit > 0:
            if not self._resource.is_current_generation(permit.generation):
                if (self._held + self._inflight) < self._limit:
                    self._resource.current.release()

    def on_task_enqueued(self) -> None:
        self._held += 1

    def on_task_dequeued(self) -> None:
        self._held = max(0, self._held - 1)
        if not self._enabled or self._limit <= 0:
            return
        if (self._held + self._inflight) < self._limit:
            self._resource.current.release()


@dataclass(slots=True)
class QueueCapacityPermit:
    limiter: QueueCapacityLimiter
    semaphore: asyncio.Semaphore
    generation: int
    finalized: bool = False

    def commit_enqueued(self) -> None:
        self.limiter.commit_enqueued_from_permit(self)

    def rollback(self) -> None:
        self.limiter.rollback_failed_enqueue_from_permit(self)
