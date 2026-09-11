"""SoAI - Database vacuum runtime and scheduling [backend/database/core/vacuum_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import cancellation_cleanup
from core.concurrency.deadlines import deadline_after
from core.concurrency.task_finalization import cancel_and_await_task
from core.concurrency.threading_async import wait_for_threading_event
from core.config.byte_sizes import MIB_BYTES
from core.database.vacuum_result import (
    DatabaseVacuumResult,
    DatabaseVacuumStartupResult,
    DatabaseVacuumStatusValue,
)
from core.di.validation import require_dependencies
from core.errors.exceptions import DatabaseError, StateError
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import build_soai_id
from core.state.errors import DatabaseTimeoutError
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.timing.constants import BACKGROUND_TIMEOUT_SEC, LONG_REQUEST_TIMEOUT_SEC
from core.timing.durations import hours_to_seconds
from core.timing.epoch import epoch_seconds_float
from database.core.paths import DatabasePaths
from database.core.vacuum import (
    VACUUM_MINIMUM_FREE_PERCENT,
    VACUUM_MINIMUM_RECLAIMABLE_BYTES,
    VacuumExecution,
    sync_vacuum,
)
from database.core.vacuum_state import (
    load_last_vacuum_timestamp_from_disk,
    persist_last_vacuum_timestamp_to_disk,
    resolve_vacuum_state_path,
)
from database.core.writer import DatabaseWriter

if TYPE_CHECKING:
    from core.tasks.protocols import TaskCancellationBinderProtocol, TaskFinalizerTrackerProtocol

__all__ = ("DatabaseVacuum", "DatabaseVacuumDependencies")

LOGGER_NAME = "SoAI.database.core.vacuum_runtime"


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
        self._startup_task: asyncio.Task[DatabaseVacuumStartupResult] | None = None
        self._active_execution: VacuumExecution | None = None
        self.last_vacuum_timestamp: float | None = None
        self.startup_result = DatabaseVacuumStartupResult(status="not_run")

    async def vacuum_database(
        self, *, require_reclaimable_space: bool = False
    ) -> DatabaseVacuumResult:
        if self._active_execution is not None:
            raise StateError("Database vacuum is already running.")
        execution = VacuumExecution(
            pending_writes=self._writer.has_pending_write_operations,
            deadline=deadline_after(LONG_REQUEST_TIMEOUT_SEC),
            require_reclaimable_space=require_reclaimable_space,
        )
        self._active_execution = execution
        try:
            try:
                result = await self._writer.queue_write_operation(
                    sync_vacuum,
                    self.db_path,
                    execution,
                    operation_timeout=LONG_REQUEST_TIMEOUT_SEC,
                )
            except asyncio.CancelledError:
                await self._stop_execution(execution)
                raise
            except DatabaseTimeoutError:
                await self._stop_execution(execution)
                raise
            if result.status is DatabaseVacuumStatusValue.COMPLETED:
                completed_at = epoch_seconds_float()
                state_path = resolve_vacuum_state_path(self.db_path, self.is_shared_memory_mode)
                timestamp_persisted = await persist_last_vacuum_timestamp_to_disk(
                    state_path, completed_at
                )
                result = replace(result, timestamp_persisted=timestamp_persisted)
                if timestamp_persisted:
                    self.last_vacuum_timestamp = completed_at
            return result
        finally:
            self._active_execution = None

    async def _stop_execution(self, execution: VacuumExecution) -> None:
        execution.cancel()
        finished = await cancellation_cleanup(
            wait_for_threading_event(execution.finished, timeout=BACKGROUND_TIMEOUT_SEC)
        )
        if not finished or execution.terminal_status is None:
            raise DatabaseError(
                "Database vacuum cleanup did not finish; database safety is unknown."
            )

    async def run_startup_maintenance(self) -> DatabaseVacuumStartupResult:
        if self._startup_task is None:
            self._startup_task = spawn_tracked_task(
                self._run_startup_maintenance(),
                name="database-vacuum-startup",
                logger=self._logger,
                cancellation_binder=self._cancellation_binder,
                cancellation_id=build_soai_id(("sys", "database", "vacuum")),
                owner="database_vacuum",
                finalizer_tracker=self._finalizer_tracker,
                owner_observes_result=True,
            )
        self.startup_result = await self._startup_task
        return self.startup_result

    async def _run_startup_maintenance(self) -> DatabaseVacuumStartupResult:
        if self._vacuum_interval_hours <= 0 or self.is_shared_memory_mode:
            return DatabaseVacuumStartupResult(status="disabled")
        state_path = resolve_vacuum_state_path(self.db_path, self.is_shared_memory_mode)
        self.last_vacuum_timestamp = await load_last_vacuum_timestamp_from_disk(state_path)
        now = epoch_seconds_float()
        if self.last_vacuum_timestamp is not None:
            elapsed = now - self.last_vacuum_timestamp
            if 0 <= elapsed < hours_to_seconds(self._vacuum_interval_hours):
                return DatabaseVacuumStartupResult(status="not_due")
            if elapsed < 0:
                self._logger.warning(
                    "Database vacuum timestamp is in the future; running startup maintenance."
                )
        self._logger.info("Checking database vacuum eligibility before runtime services...")
        try:
            result = await self.vacuum_database(require_reclaimable_space=True)
        except DatabaseTimeoutError:
            self._logger.warning(
                "Startup database vacuum timed out after safe cleanup; retrying next startup."
            )
            return DatabaseVacuumStartupResult(status="degraded", reason="timed_out")
        if result.status is DatabaseVacuumStatusValue.CANCELLED:
            raise asyncio.CancelledError()
        if result.status is DatabaseVacuumStatusValue.INSUFFICIENT_RECLAIMABLE_SPACE:
            self._logger.info(
                "Database vacuum skipped: insufficient reclaimable space (%.1f MiB); requires at least %.0f MiB and %s%% free pages.",
                result.reclaimable_bytes / MIB_BYTES,
                VACUUM_MINIMUM_RECLAIMABLE_BYTES / MIB_BYTES,
                VACUUM_MINIMUM_FREE_PERCENT,
            )
            return DatabaseVacuumStartupResult(
                status="skipped", reason=result.status.value, result=result
            )
        if result.status is not DatabaseVacuumStatusValue.COMPLETED:
            self._logger.warning(
                "Startup database vacuum did not complete (%s); retrying next startup. Elapsed: %.1fs.",
                result.status.value,
                result.elapsed_sec,
            )
            return DatabaseVacuumStartupResult(
                status="degraded", reason=result.status.value, result=result
            )
        if not result.timestamp_persisted:
            return DatabaseVacuumStartupResult(
                status="degraded", reason="timestamp_persistence_failed", result=result
            )
        self._logger.info(
            "Database vacuum completed in %.1fs. Size: %.1fMB, reclaimed: %.1fMB.",
            result.elapsed_sec,
            result.size_after_bytes / MIB_BYTES,
            result.reclaimed_bytes / MIB_BYTES,
        )
        return DatabaseVacuumStartupResult(status="completed", result=result)

    async def shutdown(self) -> None:
        if self._startup_task is not None and not self._startup_task.done():
            await cancel_and_await_task(self._startup_task)
        if self._active_execution is not None:
            await self._stop_execution(self._active_execution)
