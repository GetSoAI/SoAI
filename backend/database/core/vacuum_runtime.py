"""SoAI - Database vacuum runtime and scheduling [backend/database/core/vacuum_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import build_soai_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.timing.epoch import epoch_seconds_float
from database.core.paths import DatabasePaths
from database.core.vacuum import record_vacuum_timestamp, sync_vacuum, vacuum_loop
from database.core.writer import DatabaseWriter

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = (
    "DatabaseVacuum",
    "DatabaseVacuumDependencies",
)

LOGGER_NAME = "SoAI.database.core.vacuum_runtime"
OPERATION = "database.core.vacuum_runtime.shutdown"


@dataclass(frozen=True, slots=True)
class DatabaseVacuumDependencies:
    paths: DatabasePaths
    writer: DatabaseWriter
    vacuum_interval_hours: int
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DatabaseVacuumDependencies",
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            paths=self.paths,
            vacuum_interval_hours=self.vacuum_interval_hours,
            writer=self.writer,
        )


class DatabaseVacuum:
    def __init__(self, deps: DatabaseVacuumDependencies) -> None:
        self._logger = get_logger(LOGGER_NAME)
        self.db_path = deps.paths.db_path
        self.is_shared_memory_mode = deps.paths.is_shared_memory_mode
        self._writer = deps.writer
        self._vacuum_interval_hours = deps.vacuum_interval_hours
        self._cancellation_binder = deps.cancellation_binder
        self._finalizer_tracker = deps.finalizer_tracker
        self._vacuum_task: asyncio.Task[None] | None = None
        self._vacuum_shutdown_event: asyncio.Event | None = None
        self._vacuum_schedule_changed_event: asyncio.Event | None = None
        self.last_vacuum_timestamp: float | None = None

    def set_last_vacuum_timestamp(self, timestamp: float | None) -> None:
        self.last_vacuum_timestamp = timestamp

    async def vacuum_database(self) -> dict[str, int | float]:
        result = await self._writer.queue_write_operation(
            sync_vacuum,
            self.db_path,
            operation_timeout=300.0,
        )
        completed_at = epoch_seconds_float()
        await record_vacuum_timestamp(self, completed_at, self._vacuum_schedule_changed_event)
        return result

    async def _vacuum_loop(self) -> None:
        shutdown_event = self._vacuum_shutdown_event
        schedule_event = self._vacuum_schedule_changed_event
        if shutdown_event is None or schedule_event is None:
            return
        await vacuum_loop(
            self,
            self._vacuum_interval_hours,
            shutdown_event,
            schedule_event,
        )

    async def start_vacuum_task(self) -> None:
        if self._vacuum_interval_hours <= 0:
            self._logger.debug("Database vacuum disabled (interval <= 0).")
            return
        if self._vacuum_task and not self._vacuum_task.done():
            self._logger.debug("Database vacuum task already running.")
            return
        self._vacuum_shutdown_event = asyncio.Event()
        self._vacuum_schedule_changed_event = asyncio.Event()
        self._vacuum_task = spawn_tracked_task(
            self._vacuum_loop(),
            name="database-vacuum-periodic",
            logger=self._logger,
            cancellation_binder=self._cancellation_binder,
            cancellation_id=build_soai_id(("sys", "database", "vacuum")),
            owner="database_vacuum",
            finalizer_tracker=self._finalizer_tracker,
        )

    async def shutdown(self) -> None:
        if self._vacuum_shutdown_event:
            self._vacuum_shutdown_event.set()
        if self._vacuum_task and not self._vacuum_task.done():
            self._vacuum_task.cancel()
            try:
                await self._vacuum_task
            except asyncio.CancelledError:
                self._vacuum_task = None
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    self._logger,
                    exception,
                    message="Database vacuum task failed during shutdown (non-critical).",
                    operation=OPERATION,
                    level="debug",
                )
        self._vacuum_task = None
        self._vacuum_shutdown_event = None
        self._vacuum_schedule_changed_event = None
