"""SoAI - Scheduler start task tracking [backend/orchestrator/lifecycle/start_task_tracking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.context import create_system_cancellation_id
from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import (
    HANDLED_RUNTIME_EXCEPTIONS,
    UNEXPECTED_RUNTIME_EXCEPTIONS,
)
from core.logging.protocols import LoggerProtocol
from core.tasks.protocols import CancellationCoordinatorProtocol
from core.timing.monotonic import monotonic_ms

__all__ = ("SchedulerStartTaskTracker", "scheduler_start_cancellation_id")

OPERATION = "orchestrator.lifecycle.scheduler_start_task_tracker"


def scheduler_start_cancellation_id(plugin_name: str) -> str:
    return create_system_cancellation_id(f"scheduler_start_{plugin_name}")


class SchedulerStartTaskTracker:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def get_running(self, plugin_name: str) -> asyncio.Task[None] | None:
        task = self._tasks.get(plugin_name)
        return task if task is not None and not task.done() else None

    def track(self, plugin_name: str, task: asyncio.Task[None]) -> None:
        if self.get_running(plugin_name) is not None:
            raise StateError("A model startup task is already running for this plugin.")
        self._tasks[plugin_name] = task
        task.add_done_callback(
            lambda completed_task: self._forget_done(plugin_name, completed_task),
        )

    def _forget_done(self, plugin_name: str, completed_task: asyncio.Task[None]) -> None:
        if self._tasks.get(plugin_name) is completed_task:
            self._tasks.pop(plugin_name, None)

    async def cancel_and_wait(
        self,
        *,
        plugin_name: str,
        cancellation_coordinator: CancellationCoordinatorProtocol,
        reason: str,
        timeout_sec: float,
        logger: LoggerProtocol,
    ) -> bool:
        cancellation_id = scheduler_start_cancellation_id(plugin_name)
        await cancellation_coordinator.cancel_scope(cancellation_id, reason)
        task = self._tasks.get(plugin_name)
        if task is None or task.done():
            return True
        started_at_ms = monotonic_ms()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout_sec)
            return True
        except TimeoutError:
            elapsed_ms = monotonic_ms() - started_at_ms
            logger.error(
                "Timed out waiting %.0fms for scheduler start task cancellation for plugin '%s'.",
                elapsed_ms,
                plugin_name,
            )
            return False
        except asyncio.CancelledError as exception:
            raise_cancelled_error(exception)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Scheduler start task finished with handled exception during stop.",
                operation=OPERATION,
                details={"plugin_name": plugin_name},
                level="debug",
            )
            return True
        except SoAIError as exception:
            log_handled_exception(
                logger,
                exception,
                message="Scheduler start task finished with SoAI exception during stop.",
                operation=OPERATION,
                details={"plugin_name": plugin_name},
                level="debug",
            )
            return True
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=OPERATION)
            log_exception(
                logger,
                coerced,
                message="Scheduler start task finished with unexpected exception during stop.",
                operation=OPERATION,
                details={"plugin_name": plugin_name},
                level="warning",
            )
            return True
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=OPERATION)
            log_exception(
                logger,
                coerced,
                message="Scheduler start task finished with unclassified exception during stop.",
                operation=OPERATION,
                details={"plugin_name": plugin_name},
                level="warning",
            )
            return True
