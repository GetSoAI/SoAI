"""SoAI - Cancellation event bus fan-out [backend/core/tasks/cancellation_event_bus.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.concurrency.queue_ops import drain_queue_to_list
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.tasks.protocols import CancellationEventBusProtocol
from core.timing.epoch import epoch_seconds_float

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "CancellationEventBus",
    "CancellationEventBusDependencies",
)

OPERATION = "task_manager.notify_listeners"


@dataclass(frozen=True, slots=True)
class CancellationEventBusDependencies:
    logger: LoggerProtocol
    queue_size: int = 1

    def __post_init__(self) -> None:
        require_dependencies(
            owner="CancellationEventBusDependencies",
            logger=self.logger,
            queue_size=self.queue_size,
        )


class CancellationEventBus(CancellationEventBusProtocol):
    __slots__ = ("_listeners", "_lock", "_logger", "_queue_size")

    def __init__(self, deps: CancellationEventBusDependencies) -> None:
        self._listeners: set[asyncio.Queue[JSONDict]] = set()
        self._queue_size = max(1, int(deps.queue_size))
        self._lock = asyncio.Lock()
        self._logger = deps.logger

    @override
    async def subscribe(
        self,
    ) -> tuple[asyncio.Queue[JSONDict], Callable[[], Awaitable[None]]]:
        queue: asyncio.Queue[JSONDict] = asyncio.Queue(maxsize=self._queue_size)
        async with self._lock:
            self._listeners.add(queue)

        async def _unsubscribe() -> None:
            async with self._lock:
                self._listeners.discard(queue)

        return (queue, _unsubscribe)

    @override
    async def publish_event(self, event_type: str, cancellation_id: str | None = None) -> None:
        async with self._lock:
            if not self._listeners:
                return
            listeners: Sequence[asyncio.Queue[JSONDict]] = list(self._listeners)
        payload: JSONDict = {
            "change_type": event_type,
            "cancellation_id": cancellation_id,
            "timestamp": epoch_seconds_float(),
        }
        for queue in listeners:
            try:
                drain_queue_to_list(queue)
            except AttributeError:
                self._logger.debug(
                    "Cancellation registry listener missing queue methods; skipping listener purge.",
                )
                continue
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                self._logger.debug(
                    "Cancellation registry listener queue full; dropping update %s for %s",
                    event_type,
                    cancellation_id or "<all>",
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    self._logger,
                    exception,
                    message="Failed to notify cancellation registry listener (non-critical).",
                    operation=OPERATION,
                    level="debug",
                )

    @override
    def update_queue_size(self, size: int) -> None:
        self._queue_size = max(1, int(size))

    @override
    def get_queue_size(self) -> int:
        return self._queue_size
