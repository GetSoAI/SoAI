"""SoAI - DB writer thread entrypoint for DatabaseIOController [backend/database/io/controller/thread_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import sqlite3
import threading
from collections.abc import Callable
from queue import Queue

from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.type_catalog import TaskTypeCatalog
from core.timing.constants import SHORT_POLL_INTERVAL_SEC
from database.core.wal_lifecycle import WalLifecycleSession
from database.core.wal_lifecycle_policy import WalLifecycleDependencies
from database.core.wal_lineage_guard import WalLineageGuard
from database.io.internal_protocols import (
    DatabaseCoreIOProtocol,
    DatabaseWriteJobProtocol,
    ShutdownSentinel,
)
from database.io.metrics_monitor import DatabaseIOMetricsMonitor
from database.io.operation_status_tracker import OperationStatusTracker
from database.io.writer_loop import run_database_writer_loop
from database.migrations.runner import upgrade_database_schema_to_current

__all__ = ("run_database_writer_thread",)

LOGGER_NAME = "SoAI.database.io.thread_worker"
OPERATION_DATABASE_IO_CONTROLLER_WRITE_WORKER_CLOSE_CONNECTION = (
    "database.io.controller.write_worker.close_connection"
)
OPERATION_DATABASE_IO_WRITE_WORKER = "database_io.write_worker"
WRITER_THREAD_EXCEPTIONS: tuple[type[Exception], ...] = (
    *HANDLED_RUNTIME_EXCEPTIONS,
    sqlite3.Error,
)


def _wait_for_runtime_start(
    runtime_start_event: threading.Event,
    shutdown_event: threading.Event,
) -> bool:
    while not runtime_start_event.wait(timeout=SHORT_POLL_INTERVAL_SEC):
        if shutdown_event.is_set():
            return False
    return not shutdown_event.is_set()


def run_database_writer_thread(
    manager: DatabaseCoreIOProtocol,
    queue: Queue[DatabaseWriteJobProtocol | type[ShutdownSentinel]],
    shutdown_event: threading.Event,
    startup_complete_event: threading.Event,
    runtime_start_event: threading.Event,
    runtime_ready_event: threading.Event,
    set_init_error: Callable[[BaseException], None],
    set_shutdown_error: Callable[[BaseException], None],
    connect_timeout: float,
    write_pragmas: tuple[str, ...],
    io_sample_interval: float,
    metrics_monitor: DatabaseIOMetricsMonitor,
    bound_loop: asyncio.AbstractEventLoop | None,
    writer_session_active: threading.Event,
    writer_session_faulted: threading.Event,
    status_tracker: OperationStatusTracker,
    publish_connection: Callable[[sqlite3.Connection | None], None],
    wal_rotation_size_bytes: int,
    lineage_guard: WalLineageGuard,
    task_catalog: TaskTypeCatalog,
) -> None:
    logger = get_logger(LOGGER_NAME)
    wal_lifecycle = WalLifecycleSession(
        WalLifecycleDependencies(
            db_path=manager.db_path,
            is_shared_memory_mode=manager.is_shared_memory_mode,
            connect_timeout=connect_timeout,
            write_pragmas=write_pragmas,
            publish_connection=publish_connection,
            rotation_size_bytes=wal_rotation_size_bytes,
        ),
    )
    try:
        directory = os.path.dirname(manager.db_path)
        if directory and not directory.startswith("file:"):
            os.makedirs(directory, exist_ok=True)
        logger.debug("DB writer thread is performing initial schema creation...")
        connection = wal_lifecycle.open_writer()
        upgrade_database_schema_to_current(
            connection,
            logger=logger,
            task_catalog=task_catalog,
        )
        connection.commit()
        wal_lifecycle.open_anchor()
        logger.debug("DB writer thread successfully initialized the database schema.")
    except WRITER_THREAD_EXCEPTIONS as exception:
        try:
            wal_lifecycle.close(checkpoint_truncate=False)
        except WRITER_THREAD_EXCEPTIONS as close_exception:
            log_exception(
                logger,
                close_exception,
                message="Failed to close database connection after initialization failure.",
                operation=OPERATION_DATABASE_IO_CONTROLLER_WRITE_WORKER_CLOSE_CONNECTION,
                level="warning",
            )
        set_init_error(exception)
        startup_complete_event.set()
        return
    logger.debug("Dedicated DB writer thread started (Strictly Serialized Mode).")
    startup_complete_signaled = False
    runtime_ready_signaled = False
    try:
        startup_complete_event.set()
        startup_complete_signaled = True
        if not _wait_for_runtime_start(runtime_start_event, shutdown_event):
            return
        lineage_guard.capture_baseline()
        runtime_ready_event.set()
        runtime_ready_signaled = True
        run_database_writer_loop(
            connection=wal_lifecycle.writer_connection,
            manager=manager,
            queue=queue,
            shutdown_event=shutdown_event,
            writer_session_active=writer_session_active,
            io_sample_interval=io_sample_interval,
            metrics_monitor=metrics_monitor,
            bound_loop=bound_loop,
            status_tracker=status_tracker,
            wal_lifecycle=wal_lifecycle,
            lineage_guard=lineage_guard,
            writer_session_faulted=writer_session_faulted,
        )
    except WRITER_THREAD_EXCEPTIONS as exception:
        if runtime_ready_signaled:
            raise
        log_exception(
            logger,
            exception,
            message="Fatal error while establishing the steady-state writer connection.",
            operation=OPERATION_DATABASE_IO_WRITE_WORKER,
            level="critical",
        )
        set_init_error(exception)
        if not startup_complete_signaled:
            startup_complete_event.set()
        runtime_ready_event.set()
    finally:
        try:
            wal_lifecycle.close(
                checkpoint_truncate=(
                    runtime_ready_signaled
                    and shutdown_event.is_set()
                    and not writer_session_faulted.is_set()
                ),
            )
        except WRITER_THREAD_EXCEPTIONS as exception:
            set_shutdown_error(exception)
            log_exception(
                logger,
                exception,
                message="Failed to close database connection cleanly.",
                operation=OPERATION_DATABASE_IO_CONTROLLER_WRITE_WORKER_CLOSE_CONNECTION,
                level="warning",
            )
        logger.debug("Dedicated DB writer thread shut down.")
