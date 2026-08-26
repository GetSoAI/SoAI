"""SoAI - Database file-format identity contract [backend/database/application_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.meta.soai_v1_contract import SOAI_DATABASE_APPLICATION_ID

__all__ = (
    "enforce_database_application_id",
    "read_database_application_id",
)


def read_database_application_id(conn: sqlite3.Connection) -> int:
    cursor = conn.execute("PRAGMA application_id")
    row = cursor.fetchone()
    if row is None:
        return 0
    return int(row[0])


def _write_database_application_id(conn: sqlite3.Connection) -> None:
    conn.execute(f"PRAGMA application_id = {SOAI_DATABASE_APPLICATION_ID}")


def enforce_database_application_id(
    conn: sqlite3.Connection,
    *,
    fresh_database: bool,
) -> None:
    observed_application_id = read_database_application_id(conn)
    if observed_application_id == SOAI_DATABASE_APPLICATION_ID:
        return
    if fresh_database and observed_application_id == 0:
        _write_database_application_id(conn)
        stamped_application_id = read_database_application_id(conn)
        if stamped_application_id != SOAI_DATABASE_APPLICATION_ID:
            raise StateError(
                "Failed to stamp the SoAI database application_id.",
                details={"observed_application_id": stamped_application_id},
            )
        return
    raise StateError(
        "Refusing to use a database without the SoAI application_id.",
        details={
            "expected_application_id": SOAI_DATABASE_APPLICATION_ID,
            "observed_application_id": observed_application_id,
        },
    )
