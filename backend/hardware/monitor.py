"""SoAI - Hardware monitoring coordination [backend/hardware/monitor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from concurrent.futures import CancelledError, Future
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_system import (
    HardwareSnapshotUpdatedEvent,
    ProcessListUpdatedEvent,
)
from core.hardware.protocols import DatabaseHardwareProtocol
from core.logging.protocols import LoggerProtocol
from core.runtime.soai_identifiers import create_system_id
from core.state.errors import DatabaseUnavailableError
from core.system.processes import get_process_list
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "HardwareMonitoringCoordinator",
    "HardwareMonitoringCoordinatorDependencies",
)

OPERATION_HARDWARE_MONITOR_DONE_CALLBACK = "hardware.monitor.done_callback"


OPERATION_HARDWARE_HISTORY_COORDINATOR = "hardware.history_coordinator"
OPERATION_HARDWARE_PUBLISH_SNAPSHOT_EVENTS = "hardware.publish_snapshot_events"


_PROCESS_LIST_CACHE_TTL_SEC = 1.0


@dataclass(frozen=True, slots=True)
class HardwareMonitoringCoordinatorDependencies:
    event_bus: EventBusProtocol | None
    database_hardware: DatabaseHardwareProtocol | None
    history_enabled: bool
    retention_hours: int
    logger: LoggerProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="HardwareMonitoringCoordinatorDependencies",
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            history_enabled=self.history_enabled,
            logger=self.logger,
            retention_hours=self.retention_hours,
        )


def _create_future_done_callback(
    target_logger: LoggerProtocol,
    message: str,
    operation_base: str,
) -> Callable[[Future[None]], None]:
    def _done_callback(future: Future[None]) -> None:
        try:
            exception = future.exception()
        except CancelledError:
            return
        except RECOVERABLE_EXCEPTIONS as callback_exception:
            log_exception(
                target_logger,
                callback_exception,
                message=message,
                operation=OPERATION_HARDWARE_MONITOR_DONE_CALLBACK,
                details={"operation_base": operation_base},
                level="error",
            )
            return
        if exception is not None:
            if isinstance(exception, DatabaseUnavailableError):
                target_logger.debug(
                    "Hardware history coordinator skipped because database is unavailable.",
                )
                return
            log_exception(
                target_logger,
                exception,
                message=message,
                operation=OPERATION_HARDWARE_MONITOR_DONE_CALLBACK,
                details={"operation_base": operation_base},
                level="error",
            )

    return _done_callback


class HardwareMonitoringCoordinator:
    def __init__(self, deps: HardwareMonitoringCoordinatorDependencies) -> None:
        self._event_bus = deps.event_bus
        self._database_hardware = deps.database_hardware
        self._history_enabled = deps.history_enabled
        self._retention_hours = deps.retention_hours
        self._logger = deps.logger
        self._cancellation_binder = deps.cancellation_binder
        self._finalizer_tracker = deps.finalizer_tracker
        self._last_prune_time = 0.0
        self._process_list_lock = asyncio.Lock()
        self._process_list_cache: list[JSONDict] | None = None
        self._process_list_cache_at = 0.0

    async def _get_cached_process_list(self) -> list[JSONDict]:
        now = time.monotonic()
        cached = self._process_list_cache
        if (
            cached is not None
            and (now - self._process_list_cache_at) <= _PROCESS_LIST_CACHE_TTL_SEC
        ):
            return cached
        async with self._process_list_lock:
            now = time.monotonic()
            cached = self._process_list_cache
            if (
                cached is not None
                and (now - self._process_list_cache_at) <= _PROCESS_LIST_CACHE_TTL_SEC
            ):
                return cached
            processes = await asyncio.to_thread(get_process_list)
            self._process_list_cache = processes
            self._process_list_cache_at = time.monotonic()
            return processes

    async def _publish_snapshot_events(self, info: JSONDict) -> None:
        if not self._event_bus or self._event_bus.shutdown_event.is_set():
            return
        try:
            if self._event_bus.has_subscribers(HardwareSnapshotUpdatedEvent):
                self._event_bus.try_publish_nowait(HardwareSnapshotUpdatedEvent(snapshot=info))
            if (
                self._event_bus.has_subscribers(ProcessListUpdatedEvent)
                and not self._event_bus.shutdown_event.is_set()
            ):
                processes = await self._get_cached_process_list()
                if self._event_bus.shutdown_event.is_set():
                    return
                self._event_bus.try_publish_nowait(ProcessListUpdatedEvent(processes=processes))
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Hardware snapshot dispatch failed",
                operation=OPERATION_HARDWARE_PUBLISH_SNAPSHOT_EVENTS,
            )

    def dispatch_snapshot(self, info: JSONDict, loop: asyncio.AbstractEventLoop | None) -> None:
        if not loop or loop.is_closed():
            return
        if self._event_bus and not self._event_bus.shutdown_event.is_set():

            def _dispatch_snapshot() -> None:
                if self._event_bus is None or self._event_bus.shutdown_event.is_set():
                    return
                _ = spawn_tracked_task(
                    self._publish_snapshot_events(info),
                    name="hardware-monitoring-snapshot",
                    logger=self._logger,
                    cancellation_id=create_system_id(
                        subsystem="hardware_monitor",
                        owner="snapshot",
                        include_random_suffix=False,
                    ),
                    owner="hardware_monitor_snapshot",
                    metadata={"event": "HardwareSnapshotUpdatedEvent"},
                    cancellation_binder=self._cancellation_binder,
                    finalizer_tracker=self._finalizer_tracker,
                )

            loop.call_soon_threadsafe(_dispatch_snapshot)
        if self._history_enabled and self._database_hardware:
            try:
                history_future = asyncio.run_coroutine_threadsafe(
                    self._database_hardware.log_hardware_metrics(info),
                    loop,
                )
                history_future.add_done_callback(
                    _create_future_done_callback(
                        self._logger,
                        "Hardware history coordinator failed",
                        "hardware.history_coordinator.log_hardware_metrics",
                    ),
                )
                if time.monotonic() - self._last_prune_time > 3600:
                    prune_future = asyncio.run_coroutine_threadsafe(
                        self._database_hardware.prune_old_hardware_metrics(self._retention_hours),
                        loop,
                    )
                    prune_future.add_done_callback(
                        _create_future_done_callback(
                            self._logger,
                            "Hardware history coordinator failed",
                            "hardware.history_coordinator.prune_old_hardware_metrics",
                        ),
                    )
                    self._last_prune_time = time.monotonic()
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    self._logger,
                    exception,
                    message="Hardware history coordinator failed",
                    operation=OPERATION_HARDWARE_HISTORY_COORDINATOR,
                    level="error",
                )
