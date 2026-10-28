"""SoAI - Database integrity verification after process recovery [backend/database/core/integrity_check.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sqlite3
import threading

import aiosqlite

from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    run_idempotent_current_task_operation,
    wait_for_task_completion,
)
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_finalization import cancel_and_await_task
from core.concurrency.wait_race import wait_for_first_completed_tasks
from core.database.protocols import DatabaseReaderProtocol
from core.errors.exceptions import DatabaseError
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.state.errors import DatabaseReadCleanupError

__all__ = ("verify_database_after_unclean_shutdown",)

OPERATION = "database.core.integrity_check.verify_after_unclean_shutdown"
PROGRESS_HANDLER_INSTRUCTION_COUNT = 1000
SQLITE_CLEANUP_EXCEPTIONS: tuple[type[Exception], ...] = (
    aiosqlite.Error,
    *UNEXPECTED_RUNTIME_EXCEPTIONS,
)


async def _run_quick_check(connection: aiosqlite.Connection, logger: LoggerProtocol) -> bool:
    cursor = await connection.execute("PRAGMA quick_check")
    try:
        rows = await cursor.fetchall()
        results = tuple(row[0] for row in rows if row and isinstance(row[0], str))
        if results != ("ok",):
            logger.critical(
                "Database integrity verification failed after an unclean shutdown. SoAI will not modify the damaged database automatically. Stop SoAI, preserve a copy of the database and its WAL/SHM files, then restore a known-good SoAI backup. If no backup is usable, run the SQLite CLI .recover command into a separate database file and validate that recovered copy before replacing the original. SQLite recovery can omit or alter damaged data and may cause permanent data loss. Before returning the recovered database to service, check the host for unstable hardware or overclocking, faulty RAM, and storage device or filesystem errors that could have caused the corruption.",
            )
            raise DatabaseError(
                "Database integrity verification failed after an unclean SoAI shutdown.",
                details={"quick_check_results": list(results)},
                operation=OPERATION,
            )
        return True
    finally:
        try:
            await cursor.close()
        except SQLITE_CLEANUP_EXCEPTIONS as exception:
            raise DatabaseReadCleanupError(
                "Database integrity-check cursor cleanup failed.",
                operation=OPERATION,
                cause=exception,
            ) from exception


async def _execute_integrity_check(
    connection: aiosqlite.Connection,
    logger: LoggerProtocol,
    cancellation: threading.Event,
) -> bool:
    try:
        await connection.set_progress_handler(
            lambda: int(cancellation.is_set()), PROGRESS_HANDLER_INSTRUCTION_COUNT
        )
        try:
            return await _run_quick_check(connection, logger)
        except aiosqlite.OperationalError as exception:
            if cancellation.is_set() and exception.sqlite_errorcode == sqlite3.SQLITE_INTERRUPT:
                return False
            raise
    finally:
        try:
            await connection.set_progress_handler(lambda: 0, 0)
        except SQLITE_CLEANUP_EXCEPTIONS as exception:
            raise DatabaseReadCleanupError(
                "Database integrity-check progress handler cleanup failed.",
                operation=OPERATION,
                cause=exception,
            ) from exception


async def _settle_integrity_check(
    connection: aiosqlite.Connection,
    cancellation: threading.Event,
    operation: asyncio.Task[bool],
    stop_watcher: asyncio.Task[bool] | None,
) -> bool:
    interruption_error: Exception | None = None
    if not operation.done():
        cancellation.set()
        try:
            await connection.interrupt()
        except SQLITE_CLEANUP_EXCEPTIONS as exception:
            interruption_error = exception
    try:
        await wait_for_task_completion(operation, retain_resources_until_complete=True)
    finally:
        await cancel_and_await_task(stop_watcher)
    verified = operation.result()
    if interruption_error is not None:
        raise DatabaseReadCleanupError(
            "Database integrity-check interruption failed.",
            operation=OPERATION,
            cause=interruption_error,
        ) from interruption_error
    return verified


async def _verify_connection(
    connection: aiosqlite.Connection,
    stop_event: asyncio.Event,
    logger: LoggerProtocol,
) -> bool:
    if stop_event.is_set():
        return False
    cancellation = threading.Event()
    operation = create_ephemeral_task(
        _execute_integrity_check(connection, logger, cancellation),
        name="database-recovery-integrity-check",
        log_exceptions=False,
    )
    stop_watcher: asyncio.Task[bool] | None = None
    cancelled = False
    try:
        stop_watcher = create_ephemeral_task(
            stop_event.wait(), name="database-recovery-stop-watch", log_exceptions=False
        )
        await wait_for_first_completed_tasks({operation, stop_watcher}, cancel_pending=False)
    except asyncio.CancelledError:
        cancelled = True
    finally:
        settlement = create_ephemeral_task(
            _settle_integrity_check(connection, cancellation, operation, stop_watcher),
            name="database-recovery-cleanup",
            log_exceptions=False,
        )
        await run_idempotent_current_task_operation(lambda: asyncio.shield(settlement))
        cancelled = cancelled or current_task_has_pending_cancellation()
    if cancelled:
        raise asyncio.CancelledError()
    return settlement.result()


async def verify_database_after_unclean_shutdown(
    reader: DatabaseReaderProtocol,
    logger: LoggerProtocol,
    stop_event: asyncio.Event,
) -> bool:
    if stop_event.is_set():
        return False
    return await reader.execute_read(_verify_connection, stop_event, logger)
