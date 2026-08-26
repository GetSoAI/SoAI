"""SoAI - Asynchronous database write controller [backend/database/io/controller/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sqlite3
import threading
from queue import Queue

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.threading_async import wait_for_threading_event
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.sqlite.policy import SQLITE_JOURNAL_SIZE_LIMIT_BYTES, SQLITE_WRITE_PRAGMAS
from core.state.errors import DatabaseUnavailableError
from core.tasks.type_catalog import TaskTypeCatalog
from database.core.wal_lineage_guard import WalLineageGuard
from database.io.controller.operation_queue import DatabaseWriteOperationQueue
from database.io.controller.recovery import (
    enqueue_shutdown_sentinel,
    join_writer_thread_with_interrupt,
    raise_writer_thread_leak,
    shutdown_writer_thread_after_failed_init,
    start_writer_thread_runtime,
)
from database.io.controller.reset_state import drain_pending_items
from database.io.controller.thread_worker import run_database_writer_thread
from database.io.internal_protocols import (
    DatabaseCoreIOProtocol,
    DatabaseWriteJobProtocol,
    ShutdownSentinel,
)
from database.io.metrics_monitor import DatabaseIOMetricsMonitor
from database.io.operation_status_tracker import OperationStatusTracker

__all__ = ("DatabaseIOController",)

LOGGER_NAME = "SoAI.database.io.service"
OPERATION = "database.io.controller.shutdown.join"


class DatabaseIOController:
    def __init__(
        self,
        manager: DatabaseCoreIOProtocol,
        metrics_monitor: DatabaseIOMetricsMonitor,
        *,
        lineage_guard: WalLineageGuard,
        init_timeout: float = 30.0,
        shutdown_timeout: float = 5.0,
        connect_timeout: float = 10.0,
        write_pragmas: tuple[str, ...] = SQLITE_WRITE_PRAGMAS,
        io_sample_interval: float = 1.0,
        operation_timeout: float = 120.0,
        wal_rotation_size_bytes: int = SQLITE_JOURNAL_SIZE_LIMIT_BYTES,
        task_catalog: TaskTypeCatalog,
    ) -> None:
        self.manager = manager
        self._metrics_monitor = metrics_monitor
        self._lineage_guard = lineage_guard
        self.queue: Queue[DatabaseWriteJobProtocol | type[ShutdownSentinel]] = Queue(maxsize=10000)
        self.thread: threading.Thread | None = None
        self.active_connection: sqlite3.Connection | None = None
        self.shutdown_event = threading.Event()
        self.startup_complete_event = threading.Event()
        self.runtime_start_event = threading.Event()
        self.runtime_ready_event = threading.Event()
        self.writer_session_active = threading.Event()
        self.writer_session_active.set()
        self.writer_session_faulted = threading.Event()
        self.init_error: BaseException | None = None
        self.shutdown_error: BaseException | None = None
        self.bound_loop: asyncio.AbstractEventLoop | None = None
        self._lifecycle_lock = asyncio.Lock()
        self.init_timeout = init_timeout
        self.shutdown_timeout = shutdown_timeout
        self.connect_timeout = connect_timeout
        self.write_pragmas = write_pragmas
        self.io_sample_interval = io_sample_interval
        self.operation_timeout = operation_timeout
        self.wal_rotation_size_bytes = wal_rotation_size_bytes
        self.task_catalog = task_catalog
        self.operation_status_tracker = OperationStatusTracker()
        self.operations = DatabaseWriteOperationQueue(
            queue=self.queue,
            status_tracker=self.operation_status_tracker,
            is_running=self.is_running,
            default_operation_timeout=self.operation_timeout,
        )

    def _set_init_error(self, exception: BaseException) -> None:
        self.init_error = exception

    def _set_shutdown_error(self, exception: BaseException) -> None:
        self.shutdown_error = exception

    def publish_active_connection(self, connection: sqlite3.Connection | None) -> None:
        self.active_connection = connection

    def interrupt_active_connection(self) -> bool:
        connection = self.active_connection
        if connection is None:
            return False
        try:
            connection.interrupt()
        except sqlite3.Error:
            return False
        return True

    def _prepare_for_start(self, loop: asyncio.AbstractEventLoop) -> None:
        if self.thread is not None and not self.thread.is_alive():
            self.thread = None
            self.bound_loop = None
            self.writer_session_active.clear()
        if self.thread and self.thread.is_alive():
            if self.shutdown_event.is_set():
                raise DatabaseUnavailableError("Database core is shutting down.")
            return
        if self.bound_loop and self.bound_loop is not loop:
            raise DatabaseUnavailableError(
                "Database core is already bound to a different event loop.",
            )
        if self.writer_session_faulted.is_set():
            raise DatabaseUnavailableError("Database writer session is restarting.")
        if not self.writer_session_active.is_set():
            self.writer_session_active.set()
        self.bound_loop = loop
        self.shutdown_event.clear()
        self.startup_complete_event.clear()
        self.runtime_start_event.clear()
        self.runtime_ready_event.clear()
        self.init_error = None
        self.shutdown_error = None
        drain_pending_items(self.queue, self.operation_status_tracker)

    async def initialize(self) -> None:
        async with self._lifecycle_lock:
            await self._initialize_unlocked()

    async def _initialize_unlocked(self) -> None:
        logger = get_logger(LOGGER_NAME)
        loop = asyncio.get_running_loop()
        if self.thread and self.thread.is_alive() and not self.writer_session_active.is_set():
            joined = await join_writer_thread_with_interrupt(
                self,
                logger,
                operation="database.io.controller.initialize.session_reset",
            )
            if not joined:
                raise DatabaseUnavailableError("Database writer session reset is still closing.")
            self.thread = None
            self.bound_loop = None
        if self.thread and self.thread.is_alive():
            if self.shutdown_event.is_set():
                raise DatabaseUnavailableError("Database core is shutting down.")
            if self.bound_loop is not None and self.bound_loop is not loop:
                raise DatabaseUnavailableError(
                    "Database core is already bound to a different event loop.",
                )
            self.bound_loop = loop
            return

        self._prepare_for_start(loop)
        self.thread = threading.Thread(
            target=run_database_writer_thread,
            name="DBWriteWorker",
            daemon=True,
            args=(
                self.manager,
                self.queue,
                self.shutdown_event,
                self.startup_complete_event,
                self.runtime_start_event,
                self.runtime_ready_event,
                self._set_init_error,
                self._set_shutdown_error,
                self.connect_timeout,
                self.write_pragmas,
                self.io_sample_interval,
                self._metrics_monitor,
                self.bound_loop,
                self.writer_session_active,
                self.writer_session_faulted,
                self.operation_status_tracker,
                self.publish_active_connection,
                self.wal_rotation_size_bytes,
                self._lineage_guard,
                self.task_catalog,
            ),
        )
        self.thread.start()

        try:
            init_ok = await wait_for_threading_event(
                self.startup_complete_event,
                timeout=self.init_timeout,
            )
            if not init_ok:
                raise TimeoutError("Database writer thread init timed out.")
        except asyncio.CancelledError as exception:
            try:
                await uncancel_then_cleanup(
                    shutdown_writer_thread_after_failed_init(
                        self,
                        logger,
                        operation="database.io.controller.initialize.cancelled",
                    ),
                )
            except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
                exception.add_note(
                    f"Database writer init cancellation cleanup failed: {cleanup_exception}",
                )
            raise
        except TimeoutError as exception:
            await shutdown_writer_thread_after_failed_init(
                self,
                logger,
                operation="database.io.controller.initialize.timeout",
            )
            raise DatabaseUnavailableError("Database initialization timed out.") from exception

        init_error = self.init_error
        if init_error is not None:
            await shutdown_writer_thread_after_failed_init(
                self,
                logger,
                operation="database.io.controller.initialize.init_error",
            )
            raise DatabaseUnavailableError("Database initialization failed.") from init_error

        thread = self.thread
        if thread is None or not thread.is_alive():
            self.shutdown_event.set()
            self.thread = None
            self.bound_loop = None
            self.writer_session_active.clear()
            drain_pending_items(self.queue, self.operation_status_tracker)
            raise DatabaseUnavailableError(
                "Database writer thread terminated during initialization.",
            )
        logger.debug("Database writer thread started and initialization is complete.")

    async def start_runtime(self) -> None:
        async with self._lifecycle_lock:
            await start_writer_thread_runtime(self, get_logger(LOGGER_NAME))

    async def shutdown(self) -> None:
        async with self._lifecycle_lock:
            await self._shutdown_unlocked()

    async def _shutdown_unlocked(self) -> None:
        logger = get_logger(LOGGER_NAME)
        if not self.thread:
            self.bound_loop = None
            self.writer_session_active.clear()
            self.startup_complete_event.clear()
            self.runtime_start_event.clear()
            self.runtime_ready_event.clear()
            return
        logger.debug("Signaling DB writer thread to shut down...")
        self.writer_session_active.clear()
        self.shutdown_event.set()
        self.runtime_start_event.set()
        enqueue_shutdown_sentinel(
            self,
            logger,
            operation="database.io.controller.shutdown.queue_shutdown_sentinel",
        )
        thread = self.thread
        if thread.is_alive():
            joined = await join_writer_thread_with_interrupt(self, logger, operation=OPERATION)
            if not joined:
                raise_writer_thread_leak(self, logger, operation=OPERATION)
        self.thread = None
        self.bound_loop = None
        self.writer_session_active.clear()
        self.startup_complete_event.clear()
        self.runtime_start_event.clear()
        self.runtime_ready_event.clear()
        drain_pending_items(self.queue, self.operation_status_tracker)
        shutdown_error = self.shutdown_error
        self.shutdown_error = None
        if shutdown_error is not None:
            raise DatabaseUnavailableError("Database writer shutdown failed.") from shutdown_error

    def is_running(self) -> bool:
        return bool(
            self.thread
            and self.thread.is_alive()
            and self.writer_session_active.is_set()
            and not self.shutdown_event.is_set(),
        )
