"""SoAI - SQLite database vacuum operations and scheduling [backend/database/core/vacuum.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from core.concurrency.deadlines import MonotonicDeadline
from core.config.byte_sizes import MIB_BYTES
from core.database.vacuum_result import DatabaseVacuumResult, DatabaseVacuumStatusValue
from core.sqlite.connections import connect_sqlite
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from database.core.wal_checkpoint import run_passive_wal_checkpoint

__all__ = ("VacuumExecution", "sync_vacuum")

VACUUM_PROGRESS_HANDLER_INSTRUCTION_COUNT = 1000
VACUUM_MINIMUM_RECLAIMABLE_BYTES = 64 * MIB_BYTES
VACUUM_MINIMUM_FREE_PERCENT = 20


@dataclass(slots=True)
class VacuumExecution:
    pending_writes: Callable[[], bool]
    deadline: MonotonicDeadline
    require_reclaimable_space: bool = False
    finished: threading.Event = field(default_factory=threading.Event)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _cancelled: threading.Event = field(default_factory=threading.Event)
    _started: bool = False
    terminal_status: DatabaseVacuumStatusValue | None = None

    def begin(self) -> bool:
        with self._lock:
            if self._cancelled.is_set():
                return False
            self.finished.clear()
            self.terminal_status = None
            self._started = True
            return True

    def cancel(self) -> None:
        with self._lock:
            self._cancelled.set()
            if not self._started:
                self.terminal_status = DatabaseVacuumStatusValue.CANCELLED
                self.finished.set()

    def interruption(self) -> DatabaseVacuumStatusValue | None:
        if self._cancelled.is_set():
            return DatabaseVacuumStatusValue.CANCELLED
        if self.deadline.expired():
            return DatabaseVacuumStatusValue.TIMED_OUT
        if self.pending_writes():
            return DatabaseVacuumStatusValue.DEFERRED
        return None


def _read_pragma_int(connection: sqlite3.Connection, pragma: str) -> int:
    row = connection.execute(f"PRAGMA {pragma}").fetchone()
    if row is None:
        raise sqlite3.DatabaseError(f"SQLite PRAGMA {pragma} returned no result.")
    try:
        return int(row[0])
    except (TypeError, ValueError, OverflowError) as exception:
        raise sqlite3.DatabaseError(
            f"SQLite PRAGMA {pragma} returned an invalid result."
        ) from exception


def sync_vacuum(
    _connection: sqlite3.Connection,
    db_path: str,
    execution: VacuumExecution,
) -> DatabaseVacuumResult:
    start = time.monotonic()
    size_before = 0
    reclaimable_bytes = 0
    interruption: DatabaseVacuumStatusValue | None = None
    vacuum_connection: sqlite3.Connection | None = None
    terminal_status: DatabaseVacuumStatusValue | None = None

    def _progress_handler() -> int:
        nonlocal interruption
        interruption = execution.interruption()
        return int(interruption is not None)

    def _result(status: DatabaseVacuumStatusValue) -> DatabaseVacuumResult:
        nonlocal terminal_status
        size_after = os.path.getsize(db_path)
        terminal_status = status
        return DatabaseVacuumResult(
            status=status,
            size_before_bytes=size_before,
            size_after_bytes=size_after,
            reclaimable_bytes=reclaimable_bytes,
            reclaimed_bytes=(
                size_before - size_after if status is DatabaseVacuumStatusValue.COMPLETED else 0
            ),
            elapsed_sec=time.monotonic() - start,
        )

    try:
        if not execution.begin():
            terminal_status = DatabaseVacuumStatusValue.CANCELLED
            return DatabaseVacuumResult(DatabaseVacuumStatusValue.CANCELLED, 0, 0, 0, 0, 0.0)
        size_before = os.path.getsize(db_path)
        interruption = execution.interruption()
        if interruption is not None:
            return _result(interruption)
        vacuum_connection = connect_sqlite(
            db_path,
            timeout=min(LOCAL_IO_TIMEOUT_SEC, execution.deadline.remaining_seconds()),
            uri=db_path.startswith("file:"),
        )
        vacuum_connection.set_progress_handler(
            _progress_handler, VACUUM_PROGRESS_HANDLER_INSTRUCTION_COUNT
        )
        try:
            vacuum_connection.execute("PRAGMA optimize")
            run_passive_wal_checkpoint(vacuum_connection)
            page_size = _read_pragma_int(vacuum_connection, "page_size")
            free_pages = _read_pragma_int(vacuum_connection, "freelist_count")
            page_count = _read_pragma_int(vacuum_connection, "page_count")
            reclaimable_bytes = page_size * free_pages
            interruption = execution.interruption()
            if interruption is not None:
                return _result(interruption)
            if execution.require_reclaimable_space and (
                reclaimable_bytes < VACUUM_MINIMUM_RECLAIMABLE_BYTES
                or free_pages * 100 < page_count * VACUUM_MINIMUM_FREE_PERCENT
            ):
                return _result(DatabaseVacuumStatusValue.INSUFFICIENT_RECLAIMABLE_SPACE)
            vacuum_connection.execute("VACUUM")
            vacuum_connection.set_progress_handler(None, 0)
            run_passive_wal_checkpoint(vacuum_connection)
        except sqlite3.OperationalError as exception:
            if interruption is not None and exception.sqlite_errorcode == sqlite3.SQLITE_INTERRUPT:
                return _result(interruption)
            error_code = exception.sqlite_errorcode & 0xFF
            if error_code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                return _result(DatabaseVacuumStatusValue.BUSY)
            if error_code == sqlite3.SQLITE_FULL:
                return _result(DatabaseVacuumStatusValue.DISK_FULL)
            raise
        return _result(DatabaseVacuumStatusValue.COMPLETED)
    finally:
        cleanup_completed = False
        try:
            if vacuum_connection is not None:
                vacuum_connection.set_progress_handler(None, 0)
                vacuum_connection.close()
            cleanup_completed = True
        finally:
            execution.terminal_status = terminal_status if cleanup_completed else None
            execution.finished.set()
