"""SoAI - Database writer thread loop [backend/database/io/writer_loop.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from queue import Empty, Queue

from core.errors.exception_logging import log_exception
from core.errors.exceptions import DatabaseError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import (
    HANDLED_RUNTIME_EXCEPTIONS,
    UNEXPECTED_RUNTIME_EXCEPTIONS,
)
from core.logging.trace import get_logger
from core.state.errors import DatabaseUnavailableError
from database.core.wal_lifecycle import WalLifecycleSession
from database.core.wal_lineage_guard import WalLineageGuard
from database.io.controller.reset_state import drain_pending_items
from database.io.internal_protocols import (
    DatabaseCoreIOProtocol,
    DatabaseWriteJobProtocol,
    DatabaseWriterSessionFault,
    OperationStatus,
    ShutdownSentinel,
)
from database.io.metrics_monitor import DatabaseIOMetricsMonitor
from database.io.operation_status_tracker import OperationStatusTracker
from database.io.worker import execute_operation_with_retry
from database.io.writer_exception_reporting import report_database_writer_runtime_exception

__all__ = ("run_database_writer_loop",)

LOGGER_NAME = "SoAI.database.io.writer_loop"
OPERATION = "database_core.writer_thread"


def _raise_lineage_violations(
    lineage_guard: WalLineageGuard,
    violations: tuple[str, ...],
) -> None:
    if not violations:
        return
    lineage_guard.escalate("; ".join(violations))
    raise DatabaseWriterSessionFault(
        "Database WAL lineage was violated by external deletion or replacement of the database files.",
        details={"violations": list(violations)},
    )


def run_database_writer_loop(
    *,
    connection: sqlite3.Connection,
    manager: DatabaseCoreIOProtocol,
    queue: Queue[DatabaseWriteJobProtocol | type[ShutdownSentinel]],
    shutdown_event: threading.Event,
    writer_session_active: threading.Event | None = None,
    io_sample_interval: float,
    metrics_monitor: DatabaseIOMetricsMonitor,
    bound_loop: asyncio.AbstractEventLoop | None,
    status_tracker: OperationStatusTracker,
    wal_lifecycle: WalLifecycleSession,
    lineage_guard: WalLineageGuard,
    writer_session_faulted: threading.Event,
) -> None:
    logger = get_logger(LOGGER_NAME)
    session_active = writer_session_active
    if session_active is None:
        session_active = threading.Event()
        session_active.set()
    last_housekeeping_time: float = 0.0
    last_successful_operation_name: str | None = None
    while not shutdown_event.is_set() and session_active.is_set():
        now = time.monotonic()
        if now - last_housekeeping_time > io_sample_interval:
            last_housekeeping_time = now
            metrics_monitor.monitor_io_throughput(
                queue_size=queue.qsize(),
                bound_loop=bound_loop,
            )
            status_tracker.prune()
        operation_id: str | None = None
        job_for_error: DatabaseWriteJobProtocol | None = None
        active_job_id: str | None = None
        item_dequeued = False
        try:
            _raise_lineage_violations(lineage_guard, lineage_guard.find_violations())
            try:
                connection, rotated = wal_lifecycle.maintain()
            except DatabaseUnavailableError as exception:
                reason = "Database WAL lifecycle rotation failed"
                lineage_guard.escalate(reason)
                raise DatabaseWriterSessionFault(
                    reason,
                    details={"error": str(exception)},
                ) from exception
            if rotated:
                _raise_lineage_violations(
                    lineage_guard,
                    lineage_guard.refresh_after_rotation(),
                )
            item = queue.get(block=True, timeout=1.0)
            item_dequeued = True
            if not session_active.is_set():
                if not isinstance(item, type):
                    skipped_job = item
                    status_tracker.record_if_not_terminal(
                        skipped_job.operation_id,
                        OperationStatus.SKIPPED,
                        error_type="WriterSessionReset",
                    )
                    skipped_job.resolve_unavailable()
                continue
            if isinstance(item, type):
                if item is ShutdownSentinel:
                    break
                continue
            job: DatabaseWriteJobProtocol = item
            job_for_error = job
            operation_id = job.operation_id
            active_job_id = operation_id
            if job.is_cancelled():
                status_tracker.record_if_not_terminal(operation_id, OperationStatus.SKIPPED, None)
                logger.debug(
                    "Skipping cancelled database operation: %s (op_id=%s)",
                    job.operation_name,
                    operation_id,
                )
                continue
            if not status_tracker.claim_for_execution(operation_id, job):
                operation_status = status_tracker.get_status(operation_id)
                logger.debug(
                    "Skipping non-pending database operation: %s (op_id=%s, status=%s)",
                    job.operation_name,
                    operation_id,
                    operation_status,
                )
                continue
            if not session_active.is_set():
                status_tracker.record_if_not_terminal(
                    operation_id,
                    OperationStatus.SKIPPED,
                    error_type="WriterSessionReset",
                )
                job.resolve_unavailable()
                continue
            if execute_operation_with_retry(
                connection,
                manager,
                metrics_monitor,
                bound_loop,
                job,
                status_tracker.record_if_not_terminal,
            ):
                last_successful_operation_name = job.operation_name
        except Empty:
            continue
        except DatabaseWriterSessionFault as exception:
            logger.critical(
                "Database writer session fault. Last successful operation: %s. First failed operation: %s.",
                last_successful_operation_name or "none",
                job_for_error.operation_name if job_for_error is not None else "unknown",
            )
            if operation_id is not None:
                status_tracker.record_if_not_terminal(
                    operation_id,
                    OperationStatus.FAILED,
                    error_type=type(exception).__name__,
                )
            if job_for_error is not None and not job_for_error.is_cancelled():
                job_for_error.resolve_unavailable()
            session_active.clear()
            writer_session_faulted.set()
            drain_pending_items(queue, status_tracker)
            break
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Unexpected DB writer thread failure",
                operation=OPERATION,
            )
            if operation_id is not None:
                status_tracker.record_if_not_terminal(
                    operation_id,
                    OperationStatus.FAILED,
                    error_type=type(exception).__name__,
                )
            if job_for_error is not None and not job_for_error.is_cancelled():
                db_error = DatabaseError(
                    f"Unexpected database error in writer thread: {exception}",
                    operation="database_core.writer_thread",
                    cause=exception,
                )
                job_for_error.resolve_exception(db_error)
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            report_database_writer_runtime_exception(
                logger=logger,
                exception=exception,
                message="Critical unexpected error in DB writer loop (thread kept alive)",
                operation=OPERATION,
                level="critical",
            )
            if operation_id is not None:
                status_tracker.record_if_not_terminal(
                    operation_id,
                    OperationStatus.FAILED,
                    error_type=type(exception).__name__,
                )
            if job_for_error is not None and not job_for_error.is_cancelled():
                db_error = DatabaseError(
                    f"Critical unexpected error in writer thread: {type(exception).__name__}: {exception}",
                    operation="database_core.writer_thread",
                    cause=exception,
                )
                job_for_error.resolve_exception(db_error)
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            report_database_writer_runtime_exception(
                logger=logger,
                exception=exception,
                message="Unclassified unexpected error in DB writer loop (thread kept alive)",
                operation=OPERATION,
                level="critical",
            )
            if operation_id is not None:
                status_tracker.record_if_not_terminal(
                    operation_id,
                    OperationStatus.FAILED,
                    error_type=type(exception).__name__,
                )
            if job_for_error is not None and not job_for_error.is_cancelled():
                db_error = DatabaseError(
                    f"Unclassified unexpected error in writer thread: {type(exception).__name__}: {exception}",
                    operation="database_core.writer_thread",
                    cause=exception,
                )
                job_for_error.resolve_exception(db_error)
        finally:
            if active_job_id is not None:
                status_tracker.unregister_active_job(active_job_id)
                active_job_id = None
            if item_dequeued:
                queue.task_done()
