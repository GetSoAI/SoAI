"""SoAI - Database schema version contract enforcement [backend/database/schema_version.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.meta.soai_v1_contract import SOAI_DATABASE_SCHEMA_VERSION

__all__ = (
    "CURRENT_DATABASE_SCHEMA_VERSION",
    "ensure_supported_database_schema_version",
    "read_database_schema_version",
    "write_current_database_schema_version",
    "write_database_schema_version",
)

CURRENT_DATABASE_SCHEMA_VERSION: int = SOAI_DATABASE_SCHEMA_VERSION


def read_database_schema_version(conn: sqlite3.Connection) -> int:
    cursor = conn.execute("PRAGMA user_version")
    row = cursor.fetchone()
    if row is None:
        return 0
    return int(row[0])


def ensure_supported_database_schema_version(version: int) -> None:
    if version > CURRENT_DATABASE_SCHEMA_VERSION:
        raise StateError(
            f"Database schema version {version} is newer than supported version {CURRENT_DATABASE_SCHEMA_VERSION}.",
        )


def write_current_database_schema_version(conn: sqlite3.Connection) -> None:
    conn.execute(f"PRAGMA user_version = {CURRENT_DATABASE_SCHEMA_VERSION}")


def write_database_schema_version(conn: sqlite3.Connection, version: int) -> None:
    if version < 0:
        raise StateError(f"Invalid database schema version: {version!r}")
    ensure_supported_database_schema_version(version)
    conn.execute(f"PRAGMA user_version = {version}")
