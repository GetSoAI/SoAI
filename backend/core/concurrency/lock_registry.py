"""SoAI - Async lock registry implementation [backend/core/concurrency/lock_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import AsyncGenerator, Callable, Hashable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.lock_types import BoundedLockResult
from core.concurrency.locks import BoundedLockContext
from core.concurrency.protocols import AsyncContextManagerProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError

__all__ = (
    "TTLAsyncLockRegistry",
    "TTLAsyncLockRegistryDependencies",
)


@dataclass(frozen=True, slots=True)
class TTLAsyncLockRegistryDependencies:
    lock_factory: Callable[[], asyncio.Lock] = asyncio.Lock
    ttl_seconds: float = 3600.0
    max_size: int = 10000
    cleanup_interval_seconds: float = 300.0

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TTLAsyncLockRegistryDependencies",
            cleanup_interval_seconds=self.cleanup_interval_seconds,
            lock_factory=self.lock_factory,
            max_size=self.max_size,
            ttl_seconds=self.ttl_seconds,
        )
        if self.ttl_seconds <= 0:
            raise ValidationError("ttl_seconds must be greater than zero.")
        if self.max_size <= 0:
            raise ValidationError("max_size must be greater than zero.")
        if self.cleanup_interval_seconds <= 0:
            raise ValidationError("cleanup_interval_seconds must be greater than zero.")


class TTLAsyncLockRegistry[K: Hashable]:
    def __init__(self, deps: TTLAsyncLockRegistryDependencies) -> None:
        self._factory = deps.lock_factory
        self._ttl = float(deps.ttl_seconds)
        self._max_size = int(deps.max_size)
        self._cleanup_interval = float(deps.cleanup_interval_seconds)
        self._entries: OrderedDict[K, _TTLAsyncLockRegistryEntry] = OrderedDict()
        self._meta_lock = asyncio.Lock()
        self._capacity_condition = asyncio.Condition(self._meta_lock)
        self._last_cleanup = time.monotonic()

    def lock(self, key: K) -> AsyncContextManagerProtocol[None]:
        if key is None:
            raise ValidationError("Lock key must be provided.")
        return self._lock_context(key)

    def __getitem__(self, key: K) -> AsyncContextManagerProtocol[None]:
        if key is None:
            raise ValidationError("Lock key must be provided.")
        return self._lock_context(key)

    def get(self, key: K) -> AsyncContextManagerProtocol[None]:
        if key is None:
            raise ValidationError("Lock key must be provided.")
        return self._lock_context(key)

    def bounded_lock_for_cleanup(
        self,
        key: K,
        timeout: float,
    ) -> AsyncContextManagerProtocol[BoundedLockResult]:
        if key is None:
            raise ValidationError("Lock key must be provided.")
        return self._bounded_lock_context(key, timeout=timeout, raise_cancelled_on_exit=False)

    def bounded_lock(
        self,
        key: K,
        timeout: float,
    ) -> AsyncContextManagerProtocol[BoundedLockResult]:
        if key is None:
            raise ValidationError("Lock key must be provided.")
        return self._bounded_lock_context(key, timeout=timeout, raise_cancelled_on_exit=True)

    def is_locked(self, key: K) -> bool:
        entry = self._entries.get(key)
        if entry is None:
            return False
        return entry.lock.locked()

    def is_owned_by_current_task(self, key: K) -> bool:
        entry = self._entries.get(key)
        current_task = asyncio.current_task()
        if entry is None or current_task is None:
            return False
        return entry.owner_task_id == id(current_task) and entry.reentrancy_depth > 0

    async def remove(self, key: K) -> bool:
        async with self._meta_lock:
            while True:
                entry = self._entries.get(key)
                if entry is None:
                    return False
                if not entry.borrow_count:
                    self._entries.pop(key, None)
                    self._capacity_condition.notify_all()
                    return True
                await self._capacity_condition.wait()

    async def clear(self) -> None:
        async with self._meta_lock:
            while True:
                if not any(entry.borrow_count for entry in self._entries.values()):
                    self._entries.clear()
                    self._capacity_condition.notify_all()
                    return
                await self._capacity_condition.wait()

    def _is_entry_expired(self, *, now: float, last_used: float) -> bool:
        return (now - last_used) >= self._ttl

    def _try_cleanup_locked(self, *, now: float) -> None:
        if (now - self._last_cleanup) < self._cleanup_interval:
            return
        self._last_cleanup = now
        removed = 0
        for key, entry in list(self._entries.items()):
            if entry.borrow_count:
                continue
            if self._is_entry_expired(now=now, last_used=entry.last_used_monotonic):
                self._entries.pop(key, None)
                removed += 1
        if removed:
            self._capacity_condition.notify_all()

    def _evict_one_unborrowed_locked(self) -> bool:
        for key, entry in self._entries.items():
            if entry.borrow_count:
                continue
            self._entries.pop(key, None)
            self._capacity_condition.notify_all()
            return True
        return False

    async def _ensure_capacity_for_new_key_locked(self) -> None:
        while len(self._entries) >= self._max_size:
            now = time.monotonic()
            self._try_cleanup_locked(now=now)
            if len(self._entries) < self._max_size:
                return
            if self._evict_one_unborrowed_locked():
                continue
            await self._capacity_condition.wait()

    async def _get_or_create_entry_locked(
        self,
        *,
        key: K,
        now: float,
    ) -> _TTLAsyncLockRegistryEntry:
        existing = self._entries.get(key)
        if existing is not None:
            existing.last_used_monotonic = now
            self._entries.move_to_end(key)
            return existing
        await self._ensure_capacity_for_new_key_locked()
        created = _TTLAsyncLockRegistryEntry(
            lock=self._factory(),
            last_used_monotonic=now,
            borrow_count=0,
        )
        self._entries[key] = created
        return created

    @asynccontextmanager
    async def _lock_context(self, key: K) -> AsyncGenerator[None]:
        now = time.monotonic()
        current_task = asyncio.current_task()
        current_task_id = id(current_task) if current_task is not None else None
        async with self._meta_lock:
            self._try_cleanup_locked(now=now)
            entry = await self._get_or_create_entry_locked(key=key, now=now)
            entry.borrow_count += 1
            entry.last_used_monotonic = now
            self._entries.move_to_end(key)
        acquired = False
        reentrant_acquired = False
        try:
            if current_task_id is not None and entry.owner_task_id == current_task_id:
                async with self._meta_lock:
                    entry.reentrancy_depth += 1
                reentrant_acquired = True
            else:
                await entry.lock.acquire()
                acquired = True
                async with self._meta_lock:
                    entry.owner_task_id = current_task_id
                    entry.reentrancy_depth = 1
            yield
        finally:
            await uncancel_then_cleanup(
                self._release_entry(
                    key=key,
                    entry=entry,
                    current_task_id=current_task_id,
                    acquired=acquired,
                    reentrant_acquired=reentrant_acquired,
                ),
            )

    @asynccontextmanager
    async def _bounded_lock_context(
        self,
        key: K,
        *,
        timeout: float,
        raise_cancelled_on_exit: bool = True,
    ) -> AsyncGenerator[BoundedLockResult]:
        now = time.monotonic()
        async with self._meta_lock:
            self._try_cleanup_locked(now=now)
            entry = await self._get_or_create_entry_locked(key=key, now=now)
            entry.borrow_count += 1
            entry.last_used_monotonic = now
            self._entries.move_to_end(key)
        try:
            async with BoundedLockContext(
                entry.lock,
                timeout=timeout,
                raise_cancelled_on_exit=raise_cancelled_on_exit,
            ) as lock_result:
                yield lock_result
        finally:
            await uncancel_then_cleanup(
                self._release_entry(
                    key=key,
                    entry=entry,
                    current_task_id=None,
                    acquired=False,
                    reentrant_acquired=False,
                ),
            )

    async def _release_entry(
        self,
        *,
        key: K,
        entry: _TTLAsyncLockRegistryEntry,
        current_task_id: int | None,
        acquired: bool,
        reentrant_acquired: bool,
    ) -> None:
        release_lock = acquired
        async with self._meta_lock:
            if reentrant_acquired:
                entry.reentrancy_depth = max(0, entry.reentrancy_depth - 1)
                if entry.reentrancy_depth == 0:
                    entry.owner_task_id = None
            elif acquired:
                if current_task_id is not None and entry.owner_task_id == current_task_id:
                    entry.reentrancy_depth = max(0, entry.reentrancy_depth - 1)
                    if entry.reentrancy_depth > 0:
                        release_lock = False
                    else:
                        entry.owner_task_id = None
                else:
                    entry.owner_task_id = None
                    entry.reentrancy_depth = 0
            entry.borrow_count = max(0, int(entry.borrow_count) - 1)
            entry.last_used_monotonic = time.monotonic()
            if key in self._entries:
                self._entries.move_to_end(key)
            self._try_cleanup_locked(now=entry.last_used_monotonic)
            if len(self._entries) > self._max_size:
                self._evict_one_unborrowed_locked()
            self._capacity_condition.notify_all()
        if release_lock:
            entry.lock.release()


@dataclass(slots=True)
class _TTLAsyncLockRegistryEntry:
    lock: asyncio.Lock
    last_used_monotonic: float
    borrow_count: int
    owner_task_id: int | None = None
    reentrancy_depth: int = 0
