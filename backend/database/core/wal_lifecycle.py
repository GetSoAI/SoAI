"""SoAI - Bounded SQLite WAL lifecycle ownership [backend/database/core/wal_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sqlite3
import time

from core.errors.exceptions import DatabaseError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.sqlite.connections import connect_sqlite
from core.sqlite.file_permissions import secure_sqlite_file_permissions
from core.sqlite.policy import (
    SQLITE_READ_PRAGMAS,
    configure_sqlite_connection,
    resolve_sqlite_database_target,
)
from core.state.errors import DatabaseUnavailableError
from database.core.wal_checkpoint import run_truncate_wal_checkpoint
from database.core.wal_lifecycle_policy import (
    ANCHOR_READ_SQL,
    USER_VERSION_READ_SQL,
    WalLifecycleDependencies,
)

__all__ = ("WalLifecycleSession",)

LOGGER_NAME = "SoAI.database.core.wal_lifecycle"
WAL_LIFECYCLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *HANDLED_RUNTIME_EXCEPTIONS,
    sqlite3.Error,
)


def _close_sqlite_connection(
    connection: sqlite3.Connection,
    *,
    rollback: bool,
) -> None:
    close_exception: BaseException | None = None
    if rollback:
        try:
            connection.rollback()
        except WAL_LIFECYCLE_EXCEPTIONS as exception:
            close_exception = exception
    try:
        connection.close()
    except WAL_LIFECYCLE_EXCEPTIONS as exception:
        if close_exception is None:
            close_exception = exception
        else:
            close_exception.add_note(f"SQLite connection close also failed: {exception}")
    if close_exception is not None:
        raise close_exception


class WalLifecycleSession:
    def __init__(self, dependencies: WalLifecycleDependencies) -> None:
        self._dependencies = dependencies
        self._writer_connection: sqlite3.Connection | None = None
        self._anchor_connection: sqlite3.Connection | None = None
        self._next_rotation_check_monotonic = 0.0
        self._permissions_prepared = False

    @property
    def writer_connection(self) -> sqlite3.Connection:
        connection = self._writer_connection
        if connection is None:
            raise DatabaseUnavailableError("Database writer connection is not open.")
        return connection

    def open_writer(self) -> sqlite3.Connection:
        if self._writer_connection is not None:
            return self._writer_connection
        database_target, use_uri = resolve_sqlite_database_target(
            self._dependencies.db_path,
            is_shared_memory_mode=self._dependencies.is_shared_memory_mode,
            read_only=False,
        )
        if not self._permissions_prepared:
            secure_sqlite_file_permissions(self._dependencies.db_path, create_missing=True)
            self._permissions_prepared = True
        connection = connect_sqlite(
            database_target,
            timeout=self._dependencies.connect_timeout,
            isolation_level=None,
            uri=use_uri,
        )
        try:
            configure_sqlite_connection(connection, self._dependencies.write_pragmas)
        except WAL_LIFECYCLE_EXCEPTIONS as exception:
            try:
                _close_sqlite_connection(connection, rollback=False)
            except WAL_LIFECYCLE_EXCEPTIONS as close_exception:
                exception.add_note(f"SQLite writer open cleanup also failed: {close_exception}")
            raise
        self._writer_connection = connection
        try:
            self._dependencies.publish_connection(connection)
        except WAL_LIFECYCLE_EXCEPTIONS as exception:
            self._writer_connection = None
            try:
                _close_sqlite_connection(connection, rollback=False)
            except WAL_LIFECYCLE_EXCEPTIONS as close_exception:
                exception.add_note(f"SQLite writer publish cleanup also failed: {close_exception}")
            raise
        return connection

    def open_anchor(self) -> None:
        if self._dependencies.is_shared_memory_mode or self._anchor_connection is not None:
            return
        self._write_wal_lease_frame()
        database_target, use_uri = resolve_sqlite_database_target(
            self._dependencies.db_path,
            is_shared_memory_mode=False,
            read_only=True,
        )
        connection = connect_sqlite(
            database_target,
            timeout=self._dependencies.connect_timeout,
            isolation_level=None,
            uri=use_uri,
        )
        try:
            configure_sqlite_connection(connection, SQLITE_READ_PRAGMAS)
            connection.execute("BEGIN;")
            connection.execute(ANCHOR_READ_SQL).fetchone()
        except WAL_LIFECYCLE_EXCEPTIONS as exception:
            try:
                _close_sqlite_connection(connection, rollback=False)
            except WAL_LIFECYCLE_EXCEPTIONS as close_exception:
                exception.add_note(f"SQLite read lease open cleanup also failed: {close_exception}")
            raise
        self._anchor_connection = connection
        self._next_rotation_check_monotonic = (
            time.monotonic() + self._dependencies.rotation_check_interval_sec
        )

    def _write_wal_lease_frame(self) -> None:
        connection = self.writer_connection
        row = connection.execute(USER_VERSION_READ_SQL).fetchone()
        if row is None or len(row) != 1:
            raise sqlite3.DatabaseError("SQLite user_version returned an invalid result.")
        try:
            user_version = int(row[0])
        except (TypeError, ValueError, OverflowError) as exception:
            raise sqlite3.DatabaseError(
                "SQLite user_version returned an invalid result."
            ) from exception
        connection.execute(f"PRAGMA user_version = {user_version};")

    def maintain(self) -> tuple[sqlite3.Connection, bool]:
        connection = self.writer_connection
        try:
            rotation_is_due = self._rotation_is_due()
        except OSError as exception:
            raise DatabaseUnavailableError(
                "Database WAL lifecycle size could not be inspected.",
            ) from exception
        if not rotation_is_due:
            return (connection, False)
        self._rotate()
        return (self.writer_connection, True)

    def close(self, *, checkpoint_truncate: bool) -> None:
        close_exception: BaseException | None = None
        try:
            self._close_writer()
        except WAL_LIFECYCLE_EXCEPTIONS as exception:
            close_exception = exception
        try:
            self._close_anchor()
        except WAL_LIFECYCLE_EXCEPTIONS as exception:
            if close_exception is None:
                close_exception = exception
            else:
                close_exception.add_note(f"WAL lifecycle anchor close also failed: {exception}")
        if close_exception is not None:
            raise DatabaseError(
                "Database WAL lifecycle connections could not be closed.",
                operation="database.core.wal_lifecycle.close",
            ) from close_exception
        if checkpoint_truncate and not self._dependencies.is_shared_memory_mode:
            self._run_final_checkpoint()

    def _run_final_checkpoint(self) -> None:
        checkpoint_exception: BaseException | None = None
        try:
            connection = self.open_writer()
            self._dependencies.publish_connection(None)
            checkpoint_result = run_truncate_wal_checkpoint(connection)
            if checkpoint_result.busy:
                get_logger(LOGGER_NAME).warning(
                    "Final database WAL checkpoint remained busy with %d of %d frames checkpointed.",
                    checkpoint_result.checkpointed_frames,
                    checkpoint_result.wal_frames,
                )
        except WAL_LIFECYCLE_EXCEPTIONS as exception:
            checkpoint_exception = exception
        try:
            self._close_writer()
        except WAL_LIFECYCLE_EXCEPTIONS as exception:
            if checkpoint_exception is None:
                checkpoint_exception = exception
            else:
                checkpoint_exception.add_note(
                    f"Final checkpoint connection close also failed: {exception}"
                )
        if checkpoint_exception is not None:
            raise DatabaseError(
                "Final database WAL checkpoint could not be completed.",
                operation="database.core.wal_lifecycle.final_checkpoint",
            ) from checkpoint_exception

    def _rotation_is_due(self) -> bool:
        if self._dependencies.is_shared_memory_mode or self._anchor_connection is None:
            return False
        now = time.monotonic()
        if now < self._next_rotation_check_monotonic:
            return False
        self._next_rotation_check_monotonic = now + self._dependencies.rotation_check_interval_sec
        try:
            wal_size = os.path.getsize(f"{self._dependencies.db_path}-wal")
        except FileNotFoundError:
            return False
        return wal_size > self._dependencies.rotation_size_bytes

    def _rotate(self) -> None:
        try:
            self._close_writer()
            self._close_anchor()
            connection = self.open_writer()
            checkpoint_result = run_truncate_wal_checkpoint(connection)
            if checkpoint_result.busy:
                get_logger(LOGGER_NAME).warning(
                    "Database WAL lifecycle rotation checkpoint remained busy with %d of %d frames checkpointed; retrying in %.1f seconds.",
                    checkpoint_result.checkpointed_frames,
                    checkpoint_result.wal_frames,
                    self._dependencies.rotation_busy_retry_interval_sec,
                )
            self.open_anchor()
            if checkpoint_result.busy:
                self._next_rotation_check_monotonic = (
                    time.monotonic() + self._dependencies.rotation_busy_retry_interval_sec
                )
        except WAL_LIFECYCLE_EXCEPTIONS as exception:
            try:
                self.close(checkpoint_truncate=False)
            except DatabaseError as close_exception:
                exception.add_note(f"WAL lifecycle rotation cleanup also failed: {close_exception}")
            raise DatabaseUnavailableError(
                "Database WAL lifecycle could not be rotated safely.",
            ) from exception

    def _close_writer(self) -> None:
        connection = self._writer_connection
        if connection is None:
            return
        self._writer_connection = None
        close_exception: BaseException | None = None
        try:
            self._dependencies.publish_connection(None)
        except WAL_LIFECYCLE_EXCEPTIONS as exception:
            close_exception = exception
        try:
            _close_sqlite_connection(connection, rollback=False)
        except WAL_LIFECYCLE_EXCEPTIONS as exception:
            if close_exception is None:
                close_exception = exception
            else:
                close_exception.add_note(f"SQLite writer close also failed: {exception}")
        if close_exception is not None:
            raise close_exception

    def _close_anchor(self) -> None:
        connection = self._anchor_connection
        if connection is None:
            return
        self._anchor_connection = None
        _close_sqlite_connection(connection, rollback=True)
