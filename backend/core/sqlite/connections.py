"""SoAI - Shared sqlite3 connection policy [backend/core/sqlite/connections.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sqlite3
from typing import TYPE_CHECKING, Literal

from core.sqlite.runtime import require_safe_sqlite_runtime

if TYPE_CHECKING:
    type IsolationLevel = Literal["DEFERRED", "EXCLUSIVE", "IMMEDIATE"] | None

__all__ = ("connect_sqlite",)


def _require_existing_sqlite_database_file(db_path: str, *, uri: bool) -> None:
    if uri or db_path == ":memory:" or db_path.startswith("file:"):
        return
    if os.path.isfile(db_path):
        return
    raise sqlite3.OperationalError(f"SQLite database file does not exist: {db_path}")


def connect_sqlite(
    db_path: str,
    *,
    timeout: float,
    isolation_level: IsolationLevel = "DEFERRED",
    uri: bool = False,
    check_same_thread: bool = True,
    must_exist: bool = True,
) -> sqlite3.Connection:
    require_safe_sqlite_runtime()
    if must_exist:
        _require_existing_sqlite_database_file(db_path, uri=bool(uri))
    return sqlite3.connect(
        db_path,
        timeout=float(timeout),
        isolation_level=isolation_level,
        uri=bool(uri),
        check_same_thread=bool(check_same_thread),
    )
