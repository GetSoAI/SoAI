"""SoAI - SQLite backup source metadata and timeout sizing [backend/app/backup/sqlite_backup_source.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import os
import sqlite3
from dataclasses import dataclass

from core.config.byte_sizes import GIB_BYTES
from core.errors.exceptions import DatabaseError
from core.sqlite.connections import connect_sqlite
from core.sqlite.policy import resolve_sqlite_database_target
from core.validation.integers import is_strict_int

__all__ = (
    "SQLiteBackupSourceDetails",
    "connect_sqlite_backup_source",
    "get_sqlite_snapshot_content_bytes",
    "get_sqlite_source_physical_size_bytes",
    "load_sqlite_source_details",
    "resolve_sqlite_backup_timeout_seconds",
)

OPERATION = "app.backup.sqlite_backup.backup_sqlite_database"
_SQLITE_SOURCE_SIZE_SUFFIXES = ("", "-wal", "-journal")


@dataclass(frozen=True, slots=True)
class SQLiteBackupSourceDetails:
    path: str
    size_bytes: int
    wal_size_bytes: int
    journal_size_bytes: int
    page_size: int
    page_count: int
    freelist_count: int


def resolve_sqlite_backup_timeout_seconds(
    *,
    source_size_bytes: int,
    configured_timeout_seconds: float,
    timeout_seconds_per_gib: float,
) -> float:
    configured_timeout = _coerce_positive_finite_float(configured_timeout_seconds, 1.0)
    timeout_per_gib = _coerce_positive_finite_float(timeout_seconds_per_gib, 1.0)
    try:
        source_gib = float(max(0, source_size_bytes)) / float(GIB_BYTES)
    except OverflowError:
        source_gib = 0.0
    size_scaled_timeout = source_gib * timeout_per_gib
    if not math.isfinite(size_scaled_timeout):
        return configured_timeout
    return max(configured_timeout, size_scaled_timeout)


def _coerce_positive_finite_float(value: float, fallback: float) -> float:
    try:
        parsed = float(value)
    except OverflowError:
        return fallback
    if math.isfinite(parsed) and parsed > 0:
        return parsed
    return fallback


def connect_sqlite_backup_source(src_path: str) -> sqlite3.Connection:
    database_target, use_uri = resolve_sqlite_database_target(
        os.path.abspath(src_path),
        is_shared_memory_mode=False,
        read_only=True,
    )
    try:
        return connect_sqlite(database_target, timeout=60, uri=use_uri)
    except sqlite3.DatabaseError as exception:
        raise DatabaseError(
            "SQLite source database could not be opened.",
            details={"src_path": str(src_path)},
            operation=OPERATION,
        ) from exception


def get_sqlite_source_physical_size_bytes(src_path: str) -> int:
    total_size_bytes = 0
    for suffix in _SQLITE_SOURCE_SIZE_SUFFIXES:
        file_path = f"{src_path}{suffix}"
        if suffix:
            total_size_bytes += _get_optional_file_size(file_path)
        else:
            total_size_bytes += _get_required_file_size(file_path)
    return total_size_bytes


def get_sqlite_snapshot_content_bytes(src_path: str) -> int:
    connection = connect_sqlite_backup_source(src_path)
    try:
        details = load_sqlite_source_details(connection, src_path)
    finally:
        connection.close()
    return details.page_size * details.page_count


def load_sqlite_source_details(
    connection: sqlite3.Connection,
    src_path: str,
) -> SQLiteBackupSourceDetails:
    return SQLiteBackupSourceDetails(
        path=src_path,
        size_bytes=_get_required_file_size(src_path),
        wal_size_bytes=_get_optional_file_size(f"{src_path}-wal"),
        journal_size_bytes=_get_optional_file_size(f"{src_path}-journal"),
        page_size=_read_sqlite_pragma_int(connection, "page_size"),
        page_count=_read_sqlite_pragma_int(connection, "page_count"),
        freelist_count=_read_sqlite_pragma_int(connection, "freelist_count"),
    )


def _get_required_file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except FileNotFoundError as exception:
        raise DatabaseError(
            "SQLite source database file is missing.",
            details={"src_path": str(path)},
            operation=OPERATION,
        ) from exception
    except OSError as exception:
        raise DatabaseError(
            "SQLite source database size could not be read.",
            details={"src_path": str(path)},
            operation=OPERATION,
        ) from exception


def _get_optional_file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except FileNotFoundError:
        return 0
    except OSError as exception:
        raise DatabaseError(
            "SQLite companion file size could not be read.",
            details={"path": str(path)},
            operation=OPERATION,
        ) from exception


def _read_sqlite_pragma_int(connection: sqlite3.Connection, pragma_name: str) -> int:
    try:
        row = connection.execute(f"PRAGMA {pragma_name}").fetchone()
    except sqlite3.DatabaseError as exception:
        raise DatabaseError(
            "SQLite backup source metadata could not be read.",
            details={"pragma": pragma_name},
            operation=OPERATION,
        ) from exception
    if row is None:
        raise DatabaseError(
            "SQLite backup source metadata returned no row.",
            details={"pragma": pragma_name},
            operation=OPERATION,
        )
    value = row[0]
    if not is_strict_int(value):
        raise DatabaseError(
            "SQLite backup source metadata returned an invalid value.",
            details={"pragma": pragma_name},
            operation=OPERATION,
        )
    return value
