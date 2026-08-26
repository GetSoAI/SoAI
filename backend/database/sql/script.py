"""SoAI - SQL script execution helpers (single-statement runner) [backend/database/sql/script.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

__all__ = ("execute_sql_script",)


def execute_sql_script(conn: sqlite3.Connection, script: str) -> None:
    buffer: list[str] = []
    for char in script:
        buffer.append(char)
        if char != ";":
            continue
        candidate = "".join(buffer).strip()
        if not candidate:
            buffer.clear()
            continue
        if sqlite3.complete_statement(candidate):
            conn.execute(candidate)
            buffer.clear()
    remaining = "".join(buffer).strip()
    if not remaining:
        return
    if not sqlite3.complete_statement(remaining):
        raise ValueError("SQL script contains an incomplete statement.")
    conn.execute(remaining)
