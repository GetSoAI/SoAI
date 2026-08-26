"""SoAI - Task registry lock helpers [backend/tasks/registry/locks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from core.concurrency.protocols import AsyncContextManagerProtocol

__all__ = (
    "LazyTaskLockContext",
    "TaskLock",
)


class LazyTaskLockContext:
    __slots__ = ("_active_context", "_lock_factory")

    def __init__(self, lock_factory: Callable[[], AsyncContextManagerProtocol[None]]) -> None:
        self._lock_factory = lock_factory
        self._active_context: AsyncContextManagerProtocol[None] | None = None

    async def __aenter__(self) -> None:
        context = self._lock_factory()
        self._active_context = context
        await context.__aenter__()

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        exception_traceback: TracebackType | None,
    ) -> bool | None:
        context = self._active_context
        if context is None:
            return None
        self._active_context = None
        return await context.__aexit__(exception_type, exception_value, exception_traceback)


class TaskLock:
    __slots__ = ("lock",)

    def __init__(self, lock_factory: Callable[[], AsyncContextManagerProtocol[None]]) -> None:
        self.lock: AsyncContextManagerProtocol[None] = LazyTaskLockContext(lock_factory)
