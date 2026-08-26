"""SoAI - Shared concurrency primitives [backend/core/concurrency/locks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import weakref
from collections import OrderedDict
from collections.abc import Callable
from types import TracebackType

from core.concurrency.cancellation_cleanup import cancellation_cleanup
from core.concurrency.lock_types import BoundedLockResult
from core.timing.constants import ASYNC_POLL_SLICE_SEC, CONTROL_TIMEOUT_SEC

__all__ = (
    "AsyncRWLock",
    "AsyncRWLockReadContext",
    "AsyncRWLockWriteContext",
    "BoundedLockContext",
    "WeakAsyncLRUCache",
    "bounded_lock_for_cleanup",
)


class BoundedLockContext:
    __slots__ = (
        "_acquired",
        "_cancelled_during_acquire",
        "_lock",
        "_raise_cancelled_on_exit",
        "_timeout",
    )

    def __init__(
        self,
        lock: asyncio.Lock,
        timeout: float = ASYNC_POLL_SLICE_SEC,
        *,
        raise_cancelled_on_exit: bool = True,
    ) -> None:
        self._lock = lock
        self._timeout = max(0.0, float(timeout))
        self._acquired = False
        self._cancelled_during_acquire = False
        self._raise_cancelled_on_exit = raise_cancelled_on_exit

    async def __aenter__(self) -> BoundedLockResult:
        try:
            self._acquired = await asyncio.wait_for(self._lock.acquire(), timeout=self._timeout)
        except TimeoutError:
            self._acquired = False
        except asyncio.CancelledError:
            self._cancelled_during_acquire = True
            self._acquired = False
        return BoundedLockResult(acquired=self._acquired)

    async def __aexit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception_value: BaseException | None,
        _exception_traceback: TracebackType | None,
    ) -> None:
        if self._acquired:
            self._lock.release()
        if (
            self._raise_cancelled_on_exit
            and self._cancelled_during_acquire
            and _exception_type is None
        ):
            raise asyncio.CancelledError()
        if self._cancelled_during_acquire and not self._raise_cancelled_on_exit:
            current_task = asyncio.current_task()
            if current_task is not None and current_task.cancelling() > 0:
                current_task.uncancel()


def bounded_lock_for_cleanup(
    lock: asyncio.Lock,
    timeout: float = ASYNC_POLL_SLICE_SEC,
) -> BoundedLockContext:
    bounded_context = BoundedLockContext(lock, timeout, raise_cancelled_on_exit=False)
    return bounded_context


class AsyncRWLock:
    def __init__(self) -> None:
        self._readers = 0
        self._writer_active = False
        self._waiting_writers = 0
        self._state_lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._state_lock)

    async def acquire_read(self) -> None:
        async with self._condition:
            while self._writer_active or self._waiting_writers > 0:
                await self._condition.wait()
            self._readers += 1

    async def release_read(self) -> None:
        await cancellation_cleanup(
            self._release_read_state(),
            timeout_seconds=CONTROL_TIMEOUT_SEC,
            propagate_cancellation=True,
        )

    async def _release_read_state(self) -> None:
        async with self._state_lock:
            self._readers -= 1
            if self._readers <= 0:
                self._readers = 0
                self._condition.notify_all()

    def read_lock(self) -> AsyncRWLockReadContext:
        read_context = AsyncRWLockReadContext(self)
        return read_context

    def write_lock(self) -> AsyncRWLockWriteContext:
        write_context = AsyncRWLockWriteContext(self)
        return write_context

    async def acquire_write(self) -> None:
        async with self._condition:
            self._waiting_writers += 1
            try:
                while self._writer_active or self._readers > 0:
                    await self._condition.wait()
            except asyncio.CancelledError:
                self._waiting_writers -= 1
                self._condition.notify_all()
                raise
            self._waiting_writers -= 1
            self._writer_active = True

    async def release_write(self) -> None:
        await cancellation_cleanup(
            self._release_write_state(),
            timeout_seconds=CONTROL_TIMEOUT_SEC,
            propagate_cancellation=True,
        )

    async def _release_write_state(self) -> None:
        async with self._state_lock:
            self._writer_active = False
            self._condition.notify_all()

    async def __aenter__(self) -> AsyncRWLock:
        await self.acquire_write()
        return self

    async def __aexit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception_value: BaseException | None,
        _exception_traceback: TracebackType | None,
    ) -> None:
        await self.release_write()


class AsyncRWLockReadContext:
    def __init__(self, lock: AsyncRWLock) -> None:
        self._lock = lock

    async def __aenter__(self) -> None:
        lock = self._lock
        await lock.acquire_read()

    async def __aexit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception_value: BaseException | None,
        _exception_traceback: TracebackType | None,
    ) -> None:
        lock = self._lock
        await lock.release_read()


class AsyncRWLockWriteContext:
    def __init__(self, lock: AsyncRWLock) -> None:
        self._lock = lock

    async def __aenter__(self) -> None:
        await self._lock.acquire_write()

    async def __aexit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception_value: BaseException | None,
        _exception_traceback: TracebackType | None,
    ) -> None:
        await self._lock.release_write()


class WeakAsyncLRUCache[T]:
    def __init__(self, *, max_size: int = 1000) -> None:
        self._max_size = max(1, int(max_size))
        self._values: weakref.WeakValueDictionary[str, T] = weakref.WeakValueDictionary()
        self._lru: OrderedDict[str, None] = OrderedDict()
        self._meta_lock = asyncio.Lock()

    def _prune_locked(self) -> None:
        for key in list(self._lru.keys()):
            if key not in self._values:
                self._lru.pop(key, None)
        while len(self._lru) > self._max_size:
            self._lru.popitem(last=False)

    async def get_or_create(self, key: str, factory: Callable[[], T]) -> T:
        normalized_key = str(key)
        async with self._meta_lock:
            existing = self._values.get(normalized_key)
            if existing is not None:
                self._lru.pop(normalized_key, None)
                self._lru[normalized_key] = None
                self._prune_locked()
                return existing
            created = factory()
            self._values[normalized_key] = created
            self._lru.pop(normalized_key, None)
            self._lru[normalized_key] = None
            self._prune_locked()
            return created

    async def get(self, key: str) -> T | None:
        normalized_key = str(key)
        async with self._meta_lock:
            existing = self._values.get(normalized_key)
            if existing is None:
                self._lru.pop(normalized_key, None)
                self._prune_locked()
                return None
            self._lru.pop(normalized_key, None)
            self._lru[normalized_key] = None
            self._prune_locked()
            return existing
