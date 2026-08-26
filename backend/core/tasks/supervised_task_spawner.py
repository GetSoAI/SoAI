"""SoAI - Supervised tracked task spawner with restart backoff [backend/core/tasks/supervised_task_spawner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.awaitable_cleanup import await_wrapper
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("spawn_supervised_tracked_task",)

LOGGER_NAME = "SoAI.core.tasks.supervised_task_spawner"
OPERATION = "core.tasks.supervised_task_spawner.spawn_supervised_tracked_task"


def spawn_supervised_tracked_task(
    coro_factory: Callable[[], Awaitable[None] | Coroutine[None, None, None]],
    *,
    name: str | None = None,
    logger: LoggerProtocol | None = None,
    cancellation_binder: TaskCancellationBinderProtocol | None = None,
    cancellation_id: str | None = None,
    owner: str = "",
    metadata: dict[str, JSONValue] | None = None,
    finalizer_tracker: TaskFinalizerTrackerProtocol | None = None,
    restart_initial_delay_sec: float = 0.5,
    restart_max_delay_sec: float = 30.0,
    restart_jitter_sec: float = 0.5,
) -> asyncio.Task[None]:
    supervised_logger = logger
    supervisor_logger = get_logger(LOGGER_NAME)
    initial_delay = max(0.0, float(restart_initial_delay_sec))
    max_delay = max(initial_delay, float(restart_max_delay_sec))
    jitter = max(0.0, float(restart_jitter_sec))

    async def _supervisor() -> None:
        delay = initial_delay
        attempt = 0
        while True:
            try:
                await await_wrapper(coro_factory())
                return
            except RECOVERABLE_EXCEPTIONS as exception:
                attempt += 1
                log_exception(
                    supervisor_logger if supervised_logger is None else supervised_logger,
                    exception,
                    message="Supervised task crashed; restarting.",
                    operation=OPERATION,
                    details={
                        "attempt": int(attempt),
                        "delay_sec": float(delay),
                        "owner": str(owner),
                    },
                    level="warning",
                )
            except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
                attempt += 1
                coerced = coerce_to_soai_error(
                    exception,
                    operation="core.tasks.supervised_task_spawner.spawn_supervised_tracked_task",
                )
                log_exception(
                    supervisor_logger if supervised_logger is None else supervised_logger,
                    coerced,
                    message="Supervised task crashed (unexpected); restarting.",
                    operation=OPERATION,
                    details={
                        "attempt": int(attempt),
                        "delay_sec": float(delay),
                        "owner": str(owner),
                    },
                    level="error",
                )
            sleep_for = delay
            if jitter > 0.0:
                sleep_for += secrets.SystemRandom().uniform(0.0, jitter)
            await asyncio.sleep(max(0.0, sleep_for))
            delay = min(max_delay, max(initial_delay, delay * 2.0))

    return spawn_tracked_task(
        _supervisor(),
        name=name,
        logger=logger,
        cancellation_binder=cancellation_binder,
        cancellation_id=cancellation_id,
        owner=owner,
        metadata=metadata,
        finalizer_tracker=finalizer_tracker,
    )
