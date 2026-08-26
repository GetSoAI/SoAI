"""SoAI - SQLite write transaction execution [backend/database/core/write_transaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from database.io.internal_protocols import DatabaseWriterSessionFault
from database.operation_receipts import (
    sync_apply_acknowledged_database_write_receipts,
    sync_insert_database_write_receipt,
)

__all__ = ("run_database_write_transaction",)

LOGGER_NAME = "SoAI.database.core.write_transaction"
OPERATION_DATABASE_CORE_PROCESS_SINGLE_OPERATION = "database_core.process_single_operation"
OPERATION_DATABASE_CORE_WRITER_SAFE_ROLLBACK = "database.core.writer.safe_rollback"


def _safe_rollback(conn: sqlite3.Connection, warning_message: str) -> bool:
    logger = get_logger(LOGGER_NAME)
    try:
        conn.rollback()
        return True
    except sqlite3.Error as rollback_exception:
        coerced = coerce_to_soai_error(
            rollback_exception,
            operation=OPERATION_DATABASE_CORE_WRITER_SAFE_ROLLBACK,
        )
        log_exception(
            logger,
            coerced,
            message=warning_message,
            operation=OPERATION_DATABASE_CORE_WRITER_SAFE_ROLLBACK,
            level="warning",
        )
        return False


def run_database_write_transaction[*Ts, T](
    conn: sqlite3.Connection,
    func: Callable[[sqlite3.Connection, *Ts], T],
    args: tuple[*Ts],
    *,
    operation_id: str,
    acknowledged_operation_ids: tuple[str, ...] = (),
) -> T:
    logger = get_logger(LOGGER_NAME)
    if conn.in_transaction:
        raise DatabaseWriterSessionFault(
            "Database writer connection entered operation with an active transaction.",
            details={"operation_name": func.__name__},
        )
    try:
        conn.execute("BEGIN;")
        conn.set_authorizer(_deny_outer_transaction_control)
        try:
            result = func(conn, *args)
        finally:
            conn.set_authorizer(None)
        if not conn.in_transaction:
            raise DatabaseWriterSessionFault(
                "Database callback ended the outer transaction.",
                details={"operation_name": func.__name__},
            )
        committed_at_ms = epoch_ms()
        sync_apply_acknowledged_database_write_receipts(
            conn,
            operation_ids=acknowledged_operation_ids,
            acknowledged_at_ms=committed_at_ms,
        )
        sync_insert_database_write_receipt(
            conn,
            operation_id=operation_id,
            committed_at_ms=committed_at_ms,
        )
        conn.commit()
        return result
    except sqlite3.OperationalError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Database operational error. Rolling back.",
            operation=OPERATION_DATABASE_CORE_PROCESS_SINGLE_OPERATION,
        )
        _safe_rollback(conn, "Failed to explicitly rollback operational error transaction")
        raise
    except sqlite3.Error as exception:
        log_exception(
            logger,
            exception,
            message="Database transaction failed. Rolling back",
            operation=OPERATION_DATABASE_CORE_PROCESS_SINGLE_OPERATION,
        )
        _safe_rollback(conn, "Failed to explicitly rollback transaction")
        raise
    except ValidationError:
        _safe_rollback(conn, "Failed to rollback validation error transaction")
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Unexpected error during transaction. Rolling back",
            operation=OPERATION_DATABASE_CORE_PROCESS_SINGLE_OPERATION,
        )
        _safe_rollback(conn, "Failed to rollback transaction")
        raise
    except asyncio.CancelledError:
        _safe_rollback(conn, "Failed to rollback cancelled operation transaction")
        raise
    except (KeyboardInterrupt, SystemExit):
        _safe_rollback(conn, "Failed to rollback interrupted operation transaction")
        raise
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_DATABASE_CORE_PROCESS_SINGLE_OPERATION,
        )
        log_exception(
            logger,
            coerced,
            message="Unhandled exception during transaction. Rolling back",
            operation=OPERATION_DATABASE_CORE_PROCESS_SINGLE_OPERATION,
            level="critical",
        )
        _safe_rollback(conn, "Failed to rollback transaction after unhandled exception")
        raise
    finally:
        if conn.in_transaction and not _safe_rollback(
            conn,
            "Failed to rollback lingering transaction after database operation.",
        ):
            raise DatabaseWriterSessionFault(
                "Database writer connection remained in a transaction after rollback failure.",
                details={"operation_name": func.__name__},
            )


def _deny_outer_transaction_control(
    action_code: int,
    _argument_one: str | None,
    _argument_two: str | None,
    _database_name: str | None,
    _trigger_name: str | None,
) -> int:
    if action_code == sqlite3.SQLITE_TRANSACTION:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK
