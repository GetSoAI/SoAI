"""SoAI - SQLite writer and serialized transaction queue [backend/database/core/writer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sqlite3
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseMetricsRecorderProtocol
from core.di.validation import require_dependencies
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.sqlite.policy import build_sqlite_write_pragmas
from core.state.errors import DatabaseUnavailableError
from core.tasks.type_catalog import TaskTypeCatalog
from database.core.manager_config import DatabaseManagerSettings
from database.core.paths import DatabasePaths
from database.core.wal_lineage_guard import WalLineageGuard
from database.core.write_transaction import run_database_write_transaction
from database.io.controller.service import DatabaseIOController
from database.io.metrics_monitor import DatabaseIOMetricsMonitor

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.types.json import JSONValue

__all__ = (
    "DatabaseWriter",
    "DatabaseWriterDependencies",
)

LOGGER_NAME = "SoAI.database.core.writer"


@dataclass(frozen=True, slots=True)
class DatabaseWriterDependencies:
    paths: DatabasePaths
    config: ConfigProtocol
    settings: DatabaseManagerSettings
    task_catalog: TaskTypeCatalog
    metrics_recorder: DatabaseMetricsRecorderProtocol | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DatabaseWriterDependencies",
            config=self.config,
            paths=self.paths,
            settings=self.settings,
            task_catalog=self.task_catalog,
        )


class DatabaseWriter:
    def __init__(self, deps: DatabaseWriterDependencies) -> None:
        self.db_path = deps.paths.db_path
        self.is_shared_memory_mode = deps.paths.is_shared_memory_mode
        self.config = deps.config
        self._metrics_recorder = deps.metrics_recorder
        self._settings = deps.settings
        self._init_lock = asyncio.Lock()
        self._db_file_paths = deps.paths.db_file_paths
        self._io_metrics_monitor = DatabaseIOMetricsMonitor(
            db_file_paths=self._db_file_paths,
            config=self.config,
            metrics_enabled=True,
            metrics_recorder=self._metrics_recorder,
        )
        self.lineage_guard = WalLineageGuard(
            self._db_file_paths,
            is_shared_memory_mode=self.is_shared_memory_mode,
        )
        self._io_controller = DatabaseIOController(
            self,
            self._io_metrics_monitor,
            lineage_guard=self.lineage_guard,
            init_timeout=self._settings.writer_init_timeout,
            shutdown_timeout=self._settings.writer_shutdown_timeout,
            connect_timeout=self._settings.sqlite_connect_timeout,
            write_pragmas=build_sqlite_write_pragmas(self._settings.write_mmap_size_mb),
            io_sample_interval=self._settings.writer_sample_interval,
            operation_timeout=self._settings.writer_operation_timeout,
            task_catalog=deps.task_catalog,
        )
        self.init_complete_event = threading.Event()

    def set_metrics_recorder(self, recorder: DatabaseMetricsRecorderProtocol | None) -> None:
        self._metrics_recorder = recorder
        self._io_metrics_monitor.set_metrics_recorder(recorder)

    def bind_lineage_escalation(self, escalation: Callable[[str], None]) -> None:
        self.lineage_guard.bind_escalation(escalation)

    @property
    def metrics_recorder(self) -> DatabaseMetricsRecorderProtocol | None:
        return self._metrics_recorder

    @property
    def is_initialized(self) -> bool:
        return self.init_complete_event.is_set()

    @property
    def is_faulted(self) -> bool:
        return self._io_controller.writer_session_faulted.is_set()

    async def initialize(self) -> None:
        async with self._init_lock:
            self.init_complete_event.clear()
            try:
                await self._io_controller.initialize()
                await self._io_controller.start_runtime()
            except asyncio.CancelledError as exception:
                await uncancel_then_cleanup(
                    self._cleanup_failed_initialize(exception),
                )
                raise
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                await self._cleanup_failed_initialize(exception)
                raise
            self.init_complete_event.set()

    async def shutdown(self) -> None:
        logger = get_logger(LOGGER_NAME)
        async with self._init_lock:
            self.init_complete_event.clear()
            await self._io_controller.shutdown()
            logger.debug("Database writer thread and connection has been closed.")

    async def _cleanup_failed_initialize(
        self,
        exception: BaseException,
    ) -> None:
        try:
            await self._io_controller.shutdown()
        except HANDLED_RUNTIME_EXCEPTIONS as shutdown_exception:
            exception.add_note(
                f"Database writer shutdown after initialization failure failed: {shutdown_exception}",
            )

    def get_operation_status(self, operation_id: str) -> str | None:
        status = self._io_controller.operations.get_operation_status(operation_id)
        return status.value if status else None

    def has_pending_write_operations(self) -> bool:
        return self._io_controller.operations.has_pending_write_operations()

    async def queue_write_operation[*Ts, T](
        self,
        func: Callable[[sqlite3.Connection, *Ts], T],
        *args: *Ts,
        enqueue_timeout: float | None = None,
        operation_timeout: float | None = None,
        **named_args: JSONValue,
    ) -> T:
        if self.is_faulted:
            raise DatabaseUnavailableError("Database writer session is restarting.")
        if not self.init_complete_event.is_set():
            raise DatabaseUnavailableError(
                "Database is not yet initialized. Write operations are not available.",
            )
        if self._io_controller.shutdown_event.is_set():
            raise DatabaseUnavailableError("Database writer thread is shutting down.")
        if not self._io_controller.is_running():
            await self.initialize()

        def target_func(connection: sqlite3.Connection, *inner_args: *Ts) -> T:
            return func(connection, *inner_args, **named_args)

        if enqueue_timeout is None and operation_timeout is None:
            return await self._io_controller.operations.queue_write_operation(
                target_func,
                *args,
            )
        return await self._io_controller.operations.queue_write_operation(
            target_func,
            *args,
            enqueue_timeout=enqueue_timeout,
            operation_timeout=operation_timeout,
        )

    def process_single_operation[*Ts, T](
        self,
        conn: sqlite3.Connection,
        func: Callable[[sqlite3.Connection, *Ts], T],
        args: tuple[*Ts],
        operation_id: str,
    ) -> T:
        status_tracker = self._io_controller.operation_status_tracker
        acknowledged_operation_ids = status_tracker.snapshot_acknowledged_operation_ids()
        result = run_database_write_transaction(
            conn,
            func,
            args,
            operation_id=operation_id,
            acknowledged_operation_ids=acknowledged_operation_ids,
        )
        status_tracker.confirm_acknowledged_operation_ids(acknowledged_operation_ids)
        return result
