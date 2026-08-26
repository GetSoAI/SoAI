"""SoAI - SQLite backup support for SoAI backups [backend/app/backup/sqlite_backup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import os
import sqlite3

from app.backup.sqlite_backup_source import (
    SQLiteBackupSourceDetails,
    connect_sqlite_backup_source,
    load_sqlite_source_details,
    resolve_sqlite_backup_timeout_seconds,
)
from core.concurrency.deadlines import deadline_after
from core.errors.exceptions import DatabaseError, SoAITimeoutError, ValidationError
from core.sqlite.connections import connect_sqlite
from core.sqlite.file_permissions import secure_sqlite_file_permissions

__all__ = (
    "remove_sqlite_backup_destination_files",
    "sync_sqlite_backup",
)

OPERATION = "app.backup.sqlite_backup.backup_sqlite_database"
_SQLITE_BACKUP_PROGRESS_OPCODE_COUNT = 100
_SQLITE_DESTINATION_FILE_SUFFIXES = ("", "-wal", "-shm", "-journal")
_SQLITE_SOURCE_FILE_SUFFIXES = ("", "-wal", "-shm", "-journal")


def _require_positive_finite_float(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError(f"{field_name} must be positive.")
    try:
        numeric_value = float(value)
    except OverflowError as exception:
        raise ValidationError(f"{field_name} must be finite.") from exception
    if not math.isfinite(numeric_value):
        raise ValidationError(f"{field_name} must be finite.")
    if numeric_value <= 0:
        raise ValidationError(f"{field_name} must be positive.")
    return numeric_value


def _raise_sqlite_backup_timeout(
    src_path: str,
    dest_path: str,
    timeout_seconds: float,
    source_details: SQLiteBackupSourceDetails,
) -> None:
    raise SoAITimeoutError(
        "SQLite backup exceeded timeout.",
        details={
            "timeout_seconds": float(timeout_seconds),
            "src_path": str(src_path),
            "dest_path": str(dest_path),
            "source_size_bytes": source_details.size_bytes,
            "source_wal_size_bytes": source_details.wal_size_bytes,
            "source_journal_size_bytes": source_details.journal_size_bytes,
            "source_page_size": source_details.page_size,
            "source_page_count": source_details.page_count,
            "source_freelist_count": source_details.freelist_count,
        },
        operation=OPERATION,
    )


def _resolve_sqlite_file_set(path: str, suffixes: tuple[str, ...]) -> set[str]:
    resolved_base_path = os.path.realpath(os.path.abspath(path))
    return {
        os.path.realpath(os.path.abspath(f"{resolved_base_path}{suffix}")) for suffix in suffixes
    }


def _require_distinct_sqlite_backup_paths(src_path: str, dest_path: str) -> None:
    source_paths = _resolve_sqlite_file_set(src_path, _SQLITE_SOURCE_FILE_SUFFIXES)
    destination_paths = _resolve_sqlite_file_set(dest_path, _SQLITE_DESTINATION_FILE_SUFFIXES)
    overlapping_paths = sorted(source_paths.intersection(destination_paths))
    if overlapping_paths:
        raise ValidationError(
            "SQLite backup destination must not overlap the source database files.",
            details={
                "src_path": str(src_path),
                "dest_path": str(dest_path),
                "overlapping_paths": overlapping_paths,
            },
            operation=OPERATION,
        )


def _copy_sqlite_snapshot_into_destination(
    source: sqlite3.Connection,
    dest_path: str,
    *,
    effective_timeout_seconds: float,
    source_details: SQLiteBackupSourceDetails,
) -> None:
    deadline = deadline_after(effective_timeout_seconds)
    deadline_expired = False

    def _abort_on_deadline() -> int:
        nonlocal deadline_expired
        if deadline.expired():
            deadline_expired = True
            return 1
        return 0

    source.set_progress_handler(_abort_on_deadline, _SQLITE_BACKUP_PROGRESS_OPCODE_COUNT)
    try:
        source.execute("VACUUM INTO ?", (dest_path,))
    except sqlite3.DatabaseError as exception:
        remove_sqlite_backup_destination_files(dest_path)
        if deadline_expired:
            _raise_sqlite_backup_timeout(
                source_details.path,
                dest_path,
                effective_timeout_seconds,
                source_details,
            )
        raise DatabaseError(
            "SQLite backup failed.",
            details={
                "src_path": str(source_details.path),
                "dest_path": str(dest_path),
                "timeout_seconds": effective_timeout_seconds,
                "source_size_bytes": source_details.size_bytes,
                "source_wal_size_bytes": source_details.wal_size_bytes,
                "source_journal_size_bytes": source_details.journal_size_bytes,
            },
            operation=OPERATION,
        ) from exception
    finally:
        source.set_progress_handler(None, 0)


def remove_sqlite_backup_destination_files(dest_path: str) -> list[str]:
    removed_paths: list[str] = []
    for suffix in _SQLITE_DESTINATION_FILE_SUFFIXES:
        candidate_path = f"{dest_path}{suffix}"
        try:
            os.remove(candidate_path)
        except FileNotFoundError:
            continue
        except OSError as exception:
            raise DatabaseError(
                "SQLite backup destination file could not be removed.",
                details={"dest_path": str(dest_path), "path": candidate_path},
                operation=OPERATION,
            ) from exception
        removed_paths.append(candidate_path)
    return removed_paths


def sync_sqlite_backup(
    src_path: str,
    dest_path: str,
    *,
    timeout_seconds: float,
    timeout_seconds_per_gib: float,
) -> bool:
    if not isinstance(src_path, str) or not src_path.strip():
        raise ValidationError("src_path is required.")
    if not isinstance(dest_path, str) or not dest_path.strip():
        raise ValidationError("dest_path is required.")
    configured_timeout_seconds = _require_positive_finite_float(
        timeout_seconds,
        "timeout_seconds",
    )
    configured_timeout_seconds_per_gib = _require_positive_finite_float(
        timeout_seconds_per_gib,
        "timeout_seconds_per_gib",
    )
    _require_distinct_sqlite_backup_paths(src_path, dest_path)

    source = connect_sqlite_backup_source(src_path)
    try:
        source_details = load_sqlite_source_details(source, src_path)
        effective_timeout_seconds = resolve_sqlite_backup_timeout_seconds(
            source_size_bytes=(
                source_details.size_bytes
                + source_details.wal_size_bytes
                + source_details.journal_size_bytes
            ),
            configured_timeout_seconds=configured_timeout_seconds,
            timeout_seconds_per_gib=configured_timeout_seconds_per_gib,
        )
        remove_sqlite_backup_destination_files(dest_path)
        secure_sqlite_file_permissions(dest_path, create_missing=True)
        try:
            _copy_sqlite_snapshot_into_destination(
                source,
                dest_path,
                effective_timeout_seconds=effective_timeout_seconds,
                source_details=source_details,
            )
        finally:
            secure_sqlite_file_permissions(dest_path)
    finally:
        source.close()

    try:
        verify = connect_sqlite(dest_path, timeout=60)
    except sqlite3.DatabaseError as exception:
        raise DatabaseError(
            "SQLite backup destination could not be opened for verification.",
            details={"dest_path": str(dest_path)},
            operation=OPERATION,
        ) from exception
    try:
        try:
            result = verify.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exception:
            raise DatabaseError(
                "SQLite backup integrity check failed to execute.",
                details={"dest_path": str(dest_path)},
                operation=OPERATION,
            ) from exception
        return result is not None and result[0] == "ok"
    finally:
        verify.close()
        secure_sqlite_file_permissions(dest_path)
