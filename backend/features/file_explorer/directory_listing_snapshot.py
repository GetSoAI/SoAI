"""SoAI - Transient SQLite directory listing snapshots [backend/features/file_explorer/directory_listing_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sqlite3
import stat
import sys
import threading

from core.concurrency.cancellation import TaskCancelledError
from core.files.operations import remove_if_exists
from core.sqlite.connections import connect_sqlite
from features.file_explorer.mime import (
    classify_file_entry_type,
    detect_mime_type,
    file_entry_type_sort_rank,
)
from features.file_explorer.secure_ops.fd_ops import open_directory_fd

__all__ = ("build_directory_listing_snapshot",)

SQLITE_BUSY_TIMEOUT_SECONDS = 30.0
INSERT_BATCH_SIZE = 2048


def _raise_if_cancelled(cancellation_event: threading.Event) -> None:
    if cancellation_event.is_set():
        raise TaskCancelledError(
            "file_explorer_listing",
            "Directory listing was cancelled.",
        )


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        PRAGMA temp_store=FILE;
        CREATE TABLE entries (
            ordinal INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            is_directory INTEGER NOT NULL,
            size INTEGER NOT NULL,
            modified_at_ms INTEGER NOT NULL,
            mime_type TEXT NOT NULL,
            type_id TEXT NOT NULL,
            type_rank INTEGER NOT NULL,
            permissions TEXT NOT NULL
        );
        """,
    )


def _create_indexes(
    connection: sqlite3.Connection,
    cancellation_event: threading.Event,
) -> None:
    connection.set_progress_handler(
        lambda: int(cancellation_event.is_set()),
        1000,
    )
    try:
        connection.executescript(
            """
        CREATE INDEX entries_name_asc_idx
            ON entries (is_directory DESC, name COLLATE NOCASE ASC, name ASC, ordinal ASC);
        CREATE INDEX entries_name_desc_idx
            ON entries (is_directory DESC, name COLLATE NOCASE DESC, name ASC, ordinal ASC);
        CREATE INDEX entries_type_asc_idx
            ON entries (type_rank ASC, type_id ASC, name COLLATE NOCASE ASC, name ASC, ordinal ASC);
        CREATE INDEX entries_type_desc_idx
            ON entries (type_rank DESC, type_id DESC, name COLLATE NOCASE ASC, name ASC, ordinal ASC);
        CREATE INDEX entries_size_asc_idx
            ON entries (is_directory DESC, size ASC, name COLLATE NOCASE ASC, name ASC, ordinal ASC);
        CREATE INDEX entries_size_desc_idx
            ON entries (is_directory DESC, size DESC, name COLLATE NOCASE ASC, name ASC, ordinal ASC);
        CREATE INDEX entries_modified_asc_idx
            ON entries (is_directory DESC, modified_at_ms ASC, name COLLATE NOCASE ASC, name ASC, ordinal ASC);
        CREATE INDEX entries_modified_desc_idx
            ON entries (is_directory DESC, modified_at_ms DESC, name COLLATE NOCASE ASC, name ASC, ordinal ASC);
            """,
        )
    except sqlite3.OperationalError as exception:
        if cancellation_event.is_set():
            raise TaskCancelledError(
                "file_explorer_listing",
                "Directory listing was cancelled.",
            ) from exception
        raise
    finally:
        connection.set_progress_handler(None, 0)


def build_directory_listing_snapshot(
    *,
    snapshot_path: str,
    real_path: str,
    cancellation_event: threading.Event,
    allow_symlinks: bool,
) -> int:
    connection: sqlite3.Connection | None = None
    directory_fd: int | None = None
    completed = False
    try:
        connection = connect_sqlite(
            snapshot_path,
            timeout=SQLITE_BUSY_TIMEOUT_SECONDS,
            must_exist=False,
        )
        _create_schema(connection)
        rows: list[tuple[int, str, int, int, int, str, str, int, str]] = []
        total = 0
        scan_target: str | int = real_path
        if os.name != "nt":
            directory_fd = open_directory_fd(real_path)
            scan_target = directory_fd
        with os.scandir(scan_target) as iterator:
            for entry in iterator:
                _raise_if_cancelled(cancellation_event)
                try:
                    entry_stat = entry.stat(follow_symlinks=allow_symlinks)
                except OSError:
                    continue
                is_directory = stat.S_ISDIR(entry_stat.st_mode)
                mime_type = detect_mime_type(entry.name, is_directory)
                type_id = classify_file_entry_type(
                    entry.name,
                    mime_type,
                    is_directory=is_directory,
                )
                rows.append(
                    (
                        total,
                        entry.name,
                        int(is_directory),
                        0 if is_directory else int(entry_stat.st_size),
                        int(entry_stat.st_mtime_ns // 1_000_000),
                        mime_type,
                        type_id,
                        file_entry_type_sort_rank(type_id),
                        stat.filemode(entry_stat.st_mode),
                    ),
                )
                total += 1
                if len(rows) >= INSERT_BATCH_SIZE:
                    connection.executemany(
                        "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        rows,
                    )
                    rows.clear()
        _raise_if_cancelled(cancellation_event)
        if rows:
            connection.executemany(
                "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        _raise_if_cancelled(cancellation_event)
        _create_indexes(connection, cancellation_event)
        _raise_if_cancelled(cancellation_event)
        connection.commit()
        completed = True
        return total
    finally:
        primary_exception = sys.exception()
        cleanup_exception: Exception | None = None
        try:
            if connection is not None:
                connection.close()
        except sqlite3.Error as exception:
            cleanup_exception = exception
        try:
            if directory_fd is not None:
                os.close(directory_fd)
        except OSError as exception:
            if cleanup_exception is None:
                cleanup_exception = exception
            else:
                cleanup_exception.add_note(
                    f"Directory listing descriptor cleanup also failed: {exception}",
                )
        if not completed:
            try:
                remove_if_exists(snapshot_path)
            except OSError as exception:
                if cleanup_exception is None:
                    cleanup_exception = exception
                else:
                    cleanup_exception.add_note(
                        f"Directory listing snapshot removal also failed: {exception}",
                    )
        if cleanup_exception is not None:
            if primary_exception is None:
                raise cleanup_exception
            primary_exception.add_note(
                f"Directory listing snapshot cleanup failed: {cleanup_exception}",
            )
