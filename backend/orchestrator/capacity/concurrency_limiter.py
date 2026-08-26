"""SoAI - Authoritative plugin concurrency limiter [backend/orchestrator/capacity/concurrency_limiter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from core.errors.exceptions import ServiceUnavailableError, StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.validation.integers import is_strict_int

__all__ = ("PluginConcurrencyLimiter", "PluginConcurrencySnapshot")


@dataclass(frozen=True, slots=True)
class PluginConcurrencySnapshot:
    limit: int
    active: int
    queue: int
    accepting: bool
    lifecycle_epoch: int


@dataclass(slots=True)
class _CapacityWaiter:
    future: asyncio.Future[None]
    lifecycle_epoch: int
    granted: bool = False


class PluginConcurrencyLimiter:
    def __init__(
        self,
        plugin_name: str,
        limit: int,
        observer: Callable[[PluginConcurrencySnapshot], None] | None = None,
    ) -> None:
        self._validate_limit(limit)
        self._plugin_name = plugin_name
        self._limit = limit
        self._active_lease_count = 0
        self._waiters: deque[_CapacityWaiter] = deque()
        self._accepting = True
        self._lifecycle_epoch = 0
        self._observer = observer

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def active_lease_count(self) -> int:
        return self._active_lease_count

    @property
    def accepting(self) -> bool:
        return self._accepting

    def snapshot(self) -> PluginConcurrencySnapshot:
        return PluginConcurrencySnapshot(
            limit=self._limit,
            active=self._active_lease_count,
            queue=sum(not waiter.future.done() for waiter in self._waiters),
            accepting=self._accepting,
            lifecycle_epoch=self._lifecycle_epoch,
        )

    async def acquire(self) -> None:
        if not self._accepting:
            raise self._unavailable_error()
        if not self._waiters and self._has_available_capacity():
            self._active_lease_count += 1
            try:
                self._observe()
            except HANDLED_RUNTIME_EXCEPTIONS:
                self._active_lease_count -= 1
                raise
            return
        loop = asyncio.get_running_loop()
        waiter = _CapacityWaiter(
            future=loop.create_future(),
            lifecycle_epoch=self._lifecycle_epoch,
        )
        self._waiters.append(waiter)
        try:
            self._observe()
        except HANDLED_RUNTIME_EXCEPTIONS:
            self._waiters.remove(waiter)
            raise
        try:
            await waiter.future
        except asyncio.CancelledError:
            if waiter.granted:
                self._return_reserved_lease()
            else:
                self._remove_waiter(waiter)
                self._observe()
            raise
        if waiter.lifecycle_epoch != self._lifecycle_epoch or not self._accepting:
            self._return_reserved_lease()
            raise self._unavailable_error()

    def release(self) -> None:
        if self._active_lease_count <= 0:
            raise StateError(
                f"Plugin concurrency lease underflow for '{self._plugin_name}'.",
                operation="orchestrator.capacity.plugin_concurrency_limiter.release",
            )
        self._active_lease_count -= 1
        self._grant_waiters()
        self._observe()

    def set_limit(self, limit: int, *, publish: bool = True) -> None:
        self._validate_limit(limit)
        self._limit = limit
        self._grant_waiters()
        if publish:
            self._observe()

    def activate(self, *, publish: bool = True) -> None:
        if self._accepting:
            return
        self._accepting = True
        self._lifecycle_epoch += 1
        self._grant_waiters()
        if publish:
            self._observe()

    def publish_snapshot(self) -> None:
        self._observe()

    def deactivate(self, *, publish: bool = True) -> None:
        self._accepting = False
        self._lifecycle_epoch += 1
        while self._waiters:
            waiter = self._waiters.popleft()
            if not waiter.future.done():
                waiter.future.set_exception(self._unavailable_error())
        if publish:
            self._observe()

    def _has_available_capacity(self) -> bool:
        return self._limit == 0 or self._active_lease_count < self._limit

    def _grant_waiters(self) -> None:
        while self._accepting and self._has_available_capacity() and self._waiters:
            waiter = self._waiters.popleft()
            if waiter.future.done():
                continue
            self._active_lease_count += 1
            waiter.granted = True
            waiter.future.set_result(None)

    def _return_reserved_lease(self) -> None:
        if self._active_lease_count <= 0:
            raise StateError(
                f"Plugin concurrency reservation underflow for '{self._plugin_name}'.",
                operation="orchestrator.capacity.plugin_concurrency_limiter.cancel",
            )
        self._active_lease_count -= 1
        self._grant_waiters()
        self._observe()

    def _remove_waiter(self, waiter: _CapacityWaiter) -> None:
        try:
            self._waiters.remove(waiter)
        except ValueError:
            if waiter.granted:
                self._return_reserved_lease()

    def _observe(self) -> None:
        if self._observer is not None:
            self._observer(self.snapshot())

    def _unavailable_error(self) -> ServiceUnavailableError:
        return ServiceUnavailableError(
            f"Plugin '{self._plugin_name}' is not accepting inference work.",
            operation="orchestrator.capacity.plugin_concurrency_limiter.acquire",
            details={"plugin": self._plugin_name},
        )

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if not is_strict_int(limit) or limit < 0:
            raise ValidationError(
                "Plugin concurrency limit must be an integer greater than or equal to zero."
            )
