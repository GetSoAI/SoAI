"""SoAI - Core concurrency protocols [backend/core/concurrency/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from collections.abc import Awaitable
from types import TracebackType
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from core.concurrency.lock_types import BoundedLockResult

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "AsyncClosableIteratorProtocol",
    "AsyncContextManagerProtocol",
    "AsyncLockRegistryProtocol",
    "CancellationContextProtocol",
    "CancellationTokenProtocol",
    "QueueGetNowaitProtocol",
    "TaskDoneQueueProtocol",
)


class TaskDoneQueueProtocol(Protocol):
    def task_done(self) -> None: ...


class QueueGetNowaitProtocol[T](Protocol):
    def get_nowait(self) -> T: ...

    def task_done(self) -> None: ...


class AsyncContextManagerProtocol[T](Protocol):
    async def __aenter__(self) -> T: ...

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        exception_traceback: TracebackType | None,
        /,
    ) -> bool | None: ...


@runtime_checkable
class AsyncClosableIteratorProtocol(Protocol):
    async def aclose(self) -> None: ...


class CancellationTokenProtocol(Protocol):
    cancellation_id: str
    owner: str
    metadata: dict[str, JSONValue]
    thread_event: threading.Event

    cancellation_reason: str | None

    async def wait(self) -> None: ...

    def is_cancelled(self) -> bool | Awaitable[bool]: ...

    def raise_if_cancelled(self) -> None: ...

    def cancel(self, reason: str) -> bool: ...


class CancellationContextProtocol(Protocol):
    @property
    def cancellation_id(self) -> str | None: ...


class AsyncLockRegistryProtocol[K](Protocol):
    def lock(self, key: K) -> AsyncContextManagerProtocol[None]: ...

    def __getitem__(self, key: K) -> AsyncContextManagerProtocol[None]: ...

    def get(self, key: K) -> AsyncContextManagerProtocol[None]: ...

    def bounded_lock(
        self,
        key: K,
        timeout: float,
    ) -> AsyncContextManagerProtocol[BoundedLockResult]: ...

    def is_locked(self, key: K) -> bool: ...

    async def clear(self) -> None: ...

    async def remove(self, key: K) -> bool: ...
