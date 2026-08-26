"""SoAI - Canonical SQLite schema SQL inspection [backend/database/core/schema_sql.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
import sqlite3

SAFE_IDENTIFIER_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*\Z"


def read_schema_object_sql(
    conn: sqlite3.Connection,
    *,
    object_type: str,
    name: str,
) -> str | None:
    row = conn.execute(
        "SELECT sql FROM sqlite_schema WHERE type = ? AND name = ?",
        (object_type, name),
    ).fetchone()
    if row is None:
        return None
    sql = row[0]
    return sql if isinstance(sql, str) else None


def normalize_schema_sql(sql: str) -> str:
    normalized: list[str] = []
    index = 0
    source = sql.strip().rstrip(";")
    while index < len(source):
        character = source[index]
        if character.isspace():
            index += 1
            continue
        if character == "'":
            start = index
            index += 1
            while index < len(source):
                if source[index] != "'":
                    index += 1
                    continue
                index += 1
                if index < len(source) and source[index] == "'":
                    index += 1
                    continue
                break
            normalized.append(source[start:index])
            continue
        if character in {'"', "`"}:
            terminator = character
            end = source.find(terminator, index + 1)
            if end < 0:
                normalized.append(source[index:])
                break
            identifier = source[index + 1 : end]
            normalized.append(
                identifier
                if re.fullmatch(SAFE_IDENTIFIER_PATTERN, identifier) is not None
                else source[index : end + 1]
            )
            index = end + 1
            continue
        if character == "[":
            end = source.find("]", index + 1)
            if end < 0:
                normalized.append(source[index:])
                break
            identifier = source[index + 1 : end]
            normalized.append(
                identifier
                if re.fullmatch(SAFE_IDENTIFIER_PATTERN, identifier) is not None
                else source[index : end + 1]
            )
            index = end + 1
            continue
        normalized.append(character.lower())
        index += 1
    return "".join(normalized)


__all__ = ("normalize_schema_sql", "read_schema_object_sql")
