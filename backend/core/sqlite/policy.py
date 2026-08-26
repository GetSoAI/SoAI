"""SoAI - Shared SQLite connection policy and pragmas [backend/core/sqlite/policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sqlite3
from urllib.parse import quote

import aiosqlite

from core.sqlite.runtime import require_safe_sqlite_runtime

__all__ = (
    "SQLITE_BASE_PRAGMAS",
    "SQLITE_FTS_PRAGMAS",
    "SQLITE_JOURNAL_SIZE_LIMIT_BYTES",
    "SQLITE_READ_PRAGMAS",
    "SQLITE_WRITE_PRAGMAS",
    "build_sqlite_read_pragmas",
    "build_sqlite_write_pragmas",
    "configure_aiosqlite_connection",
    "configure_sqlite_connection",
    "resolve_sqlite_database_target",
)

SQLITE_MEBIBYTE: int = 1_048_576
SQLITE_JOURNAL_SIZE_LIMIT_BYTES: int = 67_108_864

SQLITE_BASE_PRAGMAS: tuple[str, ...] = (
    "PRAGMA synchronous = NORMAL;",
    "PRAGMA busy_timeout = 5000;",
    "PRAGMA foreign_keys = ON;",
    "PRAGMA temp_store = MEMORY;",
)

SQLITE_WRITE_PRAGMAS: tuple[str, ...] = (
    "PRAGMA journal_mode=WAL;",
    *SQLITE_BASE_PRAGMAS,
    "PRAGMA cache_size = -65536;",
    "PRAGMA wal_autocheckpoint = 8000;",
    "PRAGMA journal_size_limit = 67108864;",
)

SQLITE_READ_PRAGMAS: tuple[str, ...] = (
    *SQLITE_BASE_PRAGMAS,
    "PRAGMA cache_size = -32768;",
    "PRAGMA query_only = ON;",
)

SQLITE_FTS_PRAGMAS: tuple[str, ...] = (
    "PRAGMA busy_timeout=30000",
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
)


def _build_sqlite_mmap_pragmas(pragmas: tuple[str, ...], mmap_size_mb: int) -> tuple[str, ...]:
    if mmap_size_mb <= 0:
        return pragmas
    return (
        *pragmas,
        f"PRAGMA mmap_size = {mmap_size_mb * SQLITE_MEBIBYTE};",
    )


def build_sqlite_read_pragmas(read_mmap_size_mb: int) -> tuple[str, ...]:
    return _build_sqlite_mmap_pragmas(SQLITE_READ_PRAGMAS, read_mmap_size_mb)


def build_sqlite_write_pragmas(write_mmap_size_mb: int) -> tuple[str, ...]:
    return _build_sqlite_mmap_pragmas(SQLITE_WRITE_PRAGMAS, write_mmap_size_mb)


def configure_sqlite_connection(
    connection: sqlite3.Connection,
    pragmas: tuple[str, ...] = SQLITE_WRITE_PRAGMAS,
) -> None:
    require_safe_sqlite_runtime()
    connection.row_factory = sqlite3.Row
    for pragma in pragmas:
        connection.execute(pragma)


async def configure_aiosqlite_connection(
    connection: aiosqlite.Connection,
    pragmas: tuple[str, ...],
) -> None:
    require_safe_sqlite_runtime()
    for pragma in pragmas:
        await connection.execute(pragma)
    connection.row_factory = aiosqlite.Row


def resolve_sqlite_database_target(
    db_path: str,
    *,
    is_shared_memory_mode: bool,
    read_only: bool,
) -> tuple[str, bool]:
    if is_shared_memory_mode:
        return (db_path, True)
    if not read_only or os.name == "nt":
        return (db_path, False)
    normalized_path = quote(db_path, safe="/:\\")
    return (f"file:{normalized_path}?mode=ro", True)
