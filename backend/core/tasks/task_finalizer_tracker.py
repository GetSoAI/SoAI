"""SoAI - Task finalizer tracking for graceful shutdown [backend/core/tasks/task_finalizer_tracker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass

from core.concurrency.deadlines import deadline_remaining
from core.di.validation import require_dependencies
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.tasks.logging import log_task_exception
from core.timing.constants import (
    ASYNC_POLL_SLICE_SEC,
    SHORT_POLL_INTERVAL_SEC,
    YIELD_CONTROL_SEC,
)

__all__ = (
    "TaskFinalizerTracker",
    "TaskFinalizerTrackerDependencies",
)

_FINALIZER_LOGGER_NAME = "SoAI.core.tasks.task_finalizer_tracker"


def _log_finalizer_task_exception(task: asyncio.Task[None]) -> None:
    log_task_exception(task, get_logger(_FINALIZER_LOGGER_NAME))


async def _cancel_pending_finalizers(pending: list[asyncio.Task[None]]) -> None:
    for task in pending:
        task.cancel()
    await asyncio.wait(pending, timeout=SHORT_POLL_INTERVAL_SEC)


@dataclass(frozen=True, slots=True)
class TaskFinalizerTrackerDependencies:
    def __post_init__(self) -> None:
        require_dependencies(owner="TaskFinalizerTrackerDependencies")


class TaskFinalizerTracker:
    __slots__ = ("_finalizer_tasks", "_lock")

    def __init__(self, _deps: TaskFinalizerTrackerDependencies) -> None:
        self._finalizer_tasks: set[asyncio.Task[None]] = set()
        self._lock = threading.Lock()

    def track_finalizer(self, task: asyncio.Task[None]) -> None:
        with self._lock:
            self._finalizer_tasks.add(task)

        def _discard(done_task: asyncio.Task[None]) -> None:
            with self._lock:
                self._finalizer_tasks.discard(done_task)

        task.add_done_callback(_discard)
        task.add_done_callback(_log_finalizer_task_exception)

    async def await_all_finalizers(
        self,
        *,
        timeout: float = 5.0,
        logger: LoggerProtocol | None = None,
    ) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout))
        warned = False
        while True:
            with self._lock:
                pending = [task for task in self._finalizer_tasks if not task.done()]
            if not pending:
                return True
            remaining = deadline_remaining(deadline)
            if remaining <= 0:
                if logger and (not warned):
                    pending_names: list[str] = []
                    for task in pending[:25]:
                        try:
                            pending_names.append(task.get_name())
                        except AttributeError:
                            pending_names.append(repr(task))
                    suffix = ""
                    if len(pending) > 25:
                        suffix = f" (+{len(pending) - 25} more)"
                    logger.warning(
                        "Timed out while waiting for %d linked task finalizer(s) to complete. Pending: %s%s",
                        len(pending),
                        ", ".join(pending_names),
                        suffix,
                    )
                    warned = True
                await _cancel_pending_finalizers(pending)
                return False
            await asyncio.wait(pending, timeout=min(remaining, ASYNC_POLL_SLICE_SEC))
            await asyncio.sleep(YIELD_CONTROL_SEC)
