"""SoAI - Task backpressure and periodic scheduling utilities [backend/core/tasks/progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.task_finalization import cancel_and_await_task
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tasks.periodic import run_periodic_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "BackpressureConfig",
    "BackpressureThreshold",
    "StreamBackpressureController",
    "await_background_task_shutdown",
    "create_periodic_task",
    "run_background_periodic_task",
    "schedule_periodic_task",
)

OPERATION_CORE_TASKS_PROGRESS_AWAIT_BACKGROUND_TASK_SHUTDOWN = (
    "core.tasks.progress.await_background_task_shutdown"
)


def run_background_periodic_task(
    *,
    shutdown_event: asyncio.Event,
    interval_seconds: float,
    task: Callable[[], Awaitable[None]],
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    cancellation_id: str,
    owner: str,
    name: str,
    logger: LoggerProtocol,
    metadata: JSONDict | None = None,
    task_name: str | None = None,
    run_immediately: bool = False,
) -> asyncio.Task[None]:
    return schedule_periodic_task(
        shutdown_event=shutdown_event,
        interval_seconds=interval_seconds,
        task=task,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        cancellation_id=cancellation_id,
        owner=owner,
        name=name,
        logger=logger,
        metadata=metadata,
        task_name=task_name,
        run_immediately=run_immediately,
    )


async def await_background_task_shutdown(
    task: asyncio.Task[None] | None,
    *,
    logger: LoggerProtocol,
    operation: str,
    message: str,
    level: str = "debug",
    name: str | None = None,
    metadata: dict[str, JSONValue] | None = None,
) -> None:
    try:
        await cancel_and_await_task(task)
    except RECOVERABLE_EXCEPTIONS as exception:
        details: dict[str, JSONValue] | None = None
        normalized_name = name.strip() if name is not None else ""
        if normalized_name:
            details = {"task_name": normalized_name}
        if metadata:
            if details is None:
                details = {}
            details["task_metadata"] = dict(metadata)
        normalized_operation = operation.strip()
        if normalized_operation:
            if details is None:
                details = {}
            details["shutdown_operation"] = normalized_operation
        log_exception(
            logger,
            exception,
            message=message,
            operation=OPERATION_CORE_TASKS_PROGRESS_AWAIT_BACKGROUND_TASK_SHUTDOWN,
            level=level,
            details=details,
        )


class _DeferredAwaitable:
    __slots__ = ("_factory",)

    def __init__(self, factory: Callable[[], Awaitable[None]]) -> None:
        self._factory = factory

    def __await__(self) -> Generator[None]:
        return self._factory().__await__()


@dataclass(frozen=True, slots=True)
class BackpressureThreshold:
    queue_ratio: float
    interval_multiplier: float
    max_batch_size: int


@dataclass(frozen=True, slots=True)
class BackpressureConfig:
    base_batch_size: int = 50
    base_interval: float = 0.1
    max_interval: float = 1.0
    thresholds: tuple[BackpressureThreshold, ...] = (
        BackpressureThreshold(0.9, 5.0, 5),
        BackpressureThreshold(0.8, 3.0, 10),
        BackpressureThreshold(0.7, 2.0, 20),
    )


class StreamBackpressureController:

    __slots__ = ("_config",)

    def __init__(self, config: BackpressureConfig | None = None) -> None:
        self._config = config or BackpressureConfig()

    def compute_parameters(self, queue_depth: int, queue_max: int) -> tuple[float, int]:
        if queue_max <= 0:
            return (0.0, self._config.base_batch_size)
        ratio = queue_depth / queue_max
        for threshold in self._config.thresholds:
            if ratio >= threshold.queue_ratio:
                interval = min(
                    self._config.base_interval * threshold.interval_multiplier,
                    self._config.max_interval,
                )
                batch = max(1, min(self._config.base_batch_size, threshold.max_batch_size))
                return (interval, batch)
        return (0.0, self._config.base_batch_size)


def schedule_periodic_task(
    *,
    shutdown_event: asyncio.Event,
    interval_seconds: float,
    task: Callable[[], Awaitable[None]],
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    cancellation_id: str,
    owner: str,
    name: str,
    logger: LoggerProtocol,
    metadata: JSONDict | None = None,
    task_name: str | None = None,
    run_immediately: bool = False,
) -> asyncio.Task[None]:
    periodic_coro = run_periodic_task(
        shutdown_event,
        interval_seconds,
        task,
        logger=logger,
        task_name=task_name or name,
        run_immediately=run_immediately,
    )
    return spawn_tracked_task(
        periodic_coro,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        cancellation_id=cancellation_id,
        owner=owner,
        name=name,
        logger=logger,
        metadata=metadata,
    )


def create_periodic_task(
    *,
    shutdown_event: asyncio.Event,
    interval_seconds: float,
    task: Callable[[], Awaitable[None]],
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: LoggerProtocol,
    managed_task_name: str,
    periodic_task_name: str | None = None,
    cancellation_id: str,
    owner: str,
    metadata: JSONDict | None = None,
    run_immediately: bool = False,
) -> asyncio.Task[None]:
    cancellation_id_value = normalize_cancellation_id(cancellation_id)
    if not cancellation_id_value:
        raise ValidationError("cancellation_id is required for periodic tasks.")
    owner_value = str(owner or "").strip()
    if not owner_value:
        raise ValidationError("owner is required for periodic tasks.")
    loop_name = periodic_task_name or managed_task_name

    def _build_periodic_coro() -> Awaitable[None]:
        return run_periodic_task(
            shutdown_event,
            interval_seconds,
            task,
            logger=logger,
            task_name=loop_name,
            run_immediately=run_immediately,
        )

    return spawn_tracked_task(
        _DeferredAwaitable(_build_periodic_coro),
        name=managed_task_name,
        logger=logger,
        cancellation_binder=cancellation_binder,
        cancellation_id=cancellation_id_value,
        owner=owner_value,
        metadata=metadata,
        finalizer_tracker=finalizer_tracker,
    )
