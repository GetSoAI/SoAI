"""SoAI - Database write worker execution logic [backend/database/io/worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable

from core.errors.exception_logging import log_exception
from core.errors.exceptions import DatabaseError, SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import (
    HANDLED_RUNTIME_EXCEPTIONS,
    UNEXPECTED_RUNTIME_EXCEPTIONS,
)
from core.logging.trace import get_logger
from core.timing.monotonic import monotonic_ms
from core.timing.retry_backoff import compute_uniform_delay_seconds
from core.timing.sleep import sleep_seconds
from database.io.internal_protocols import (
    DatabaseCoreIOProtocol,
    DatabaseWriteJobProtocol,
    DatabaseWriterSessionFault,
    OperationStatus,
)
from database.io.metrics_monitor import DatabaseIOMetricsMonitor
from database.io.writer_exception_reporting import report_database_writer_runtime_exception

__all__ = ("execute_operation_with_retry",)

LOGGER_NAME = "SoAI.database.io.worker"
OPERATION = "database_core.writer_thread"


RETRIABLE_SQLITE_ERRORS = frozenset(
    (
        "database is locked",
        "database table is locked",
        "lock timeout",
        "busy",
    ),
)


def _is_retriable_operational_error(exception: sqlite3.OperationalError) -> bool:
    message = str(exception).lower()
    return any(pattern in message for pattern in RETRIABLE_SQLITE_ERRORS)


def execute_operation_with_retry(
    conn: sqlite3.Connection,
    manager: DatabaseCoreIOProtocol,
    metrics_monitor: DatabaseIOMetricsMonitor,
    bound_loop: asyncio.AbstractEventLoop | None,
    job: DatabaseWriteJobProtocol,
    record_status: Callable[[str, OperationStatus, str | None], bool | None],
    retries: int = 3,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    operation_id = job.operation_id
    for attempt in range(retries):
        if job.is_cancelled():
            logger.debug(
                "Aborting database operation mid-retry due to cancellation: %s (op_id=%s)",
                job.operation_name,
                operation_id,
            )
            record_status(operation_id, OperationStatus.SKIPPED, None)
            return False
        op_start_time = monotonic_ms()
        try:
            job.execute_once(conn, manager)
            record_status(operation_id, OperationStatus.COMMITTED, None)
            return True
        except sqlite3.OperationalError as exception:
            if not _is_retriable_operational_error(exception):
                log_exception(
                    logger,
                    exception,
                    message="Non-retriable DB operational error, failing immediately",
                    operation=OPERATION,
                )
                record_status(
                    operation_id,
                    OperationStatus.FAILED,
                    type(exception).__name__,
                )
                if not job.is_cancelled():
                    db_error = DatabaseError(
                        f"Database operational error: {exception}",
                        operation="database_core.writer_thread",
                        cause=exception,
                    )
                    job.resolve_exception(db_error)
                return False
            logger.warning(
                "DB transaction conflict (attempt %s/%s), retrying after a short delay: %s",
                attempt + 1,
                retries,
                str(exception),
            )
            if attempt < retries - 1:
                sleep_seconds(
                    compute_uniform_delay_seconds(
                        minimum_seconds=0.05,
                        maximum_seconds=0.2,
                    ),
                )
        except sqlite3.Error as exception:
            log_exception(
                logger,
                exception,
                message="Database transaction failed",
                operation=OPERATION,
            )
            record_status(
                operation_id,
                OperationStatus.FAILED,
                type(exception).__name__,
            )
            if not job.is_cancelled():
                db_error = DatabaseError(
                    f"Database transaction failed: {exception}",
                    operation="database_core.writer_thread",
                    cause=exception,
                )
                job.resolve_exception(db_error)
            return False
        except DatabaseWriterSessionFault:
            raise
        except SoAIError as exception:
            record_status(
                operation_id,
                OperationStatus.FAILED,
                type(exception).__name__,
            )
            if not job.is_cancelled():
                job.resolve_exception(exception)
            return False
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Unexpected error during transaction",
                operation=OPERATION,
            )
            record_status(
                operation_id,
                OperationStatus.FAILED,
                type(exception).__name__,
            )
            if not job.is_cancelled():
                db_error = DatabaseError(
                    f"Unexpected database error during transaction: {exception}",
                    operation="database_core.writer_thread",
                    cause=exception,
                )
                job.resolve_exception(db_error)
            return False
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            report_database_writer_runtime_exception(
                logger=logger,
                exception=exception,
                message="Critical unexpected error during DB operation (writer thread kept alive)",
                operation=OPERATION,
                level="critical",
            )
            record_status(
                operation_id,
                OperationStatus.FAILED,
                type(exception).__name__,
            )
            if not job.is_cancelled():
                db_error = DatabaseError(
                    f"Critical unexpected error during database operation: {type(exception).__name__}: {exception}",
                    operation="database_core.writer_thread",
                    cause=exception,
                )
                job.resolve_exception(db_error)
            return False
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            report_database_writer_runtime_exception(
                logger=logger,
                exception=exception,
                message="Unclassified unexpected error during DB operation (writer thread kept alive)",
                operation=OPERATION,
                level="critical",
            )
            record_status(
                operation_id,
                OperationStatus.FAILED,
                type(exception).__name__,
            )
            if not job.is_cancelled():
                db_error = DatabaseError(
                    f"Unclassified unexpected error during database operation: {type(exception).__name__}: {exception}",
                    operation="database_core.writer_thread",
                    cause=exception,
                )
                job.resolve_exception(db_error)
            return False
        finally:
            metrics_monitor.record_write_duration(
                op_start_time,
                bound_loop=bound_loop,
            )
    logger.error("DB write operation failed after %s retries.", retries)
    record_status(operation_id, OperationStatus.FAILED, "RetryExhausted")
    if not job.is_cancelled():
        db_error = DatabaseError(
            f"Database operation failed after {retries} retries due to lock contention.",
            operation="database_core.writer_thread",
        )
        job.resolve_exception(db_error)
    return False
