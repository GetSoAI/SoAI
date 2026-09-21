"""SoAI - Exact current database schema validation [backend/database/current_schema_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from core.errors.exceptions import StateError
from core.tasks.type_catalog import TaskTypeCatalog
from database.core.schema_sql import normalize_schema_sql
from database.current_schema_objects import apply_current_schema_objects
from database.webui_identity_schema_validation import validate_current_webui_identity_rows

__all__ = ("SchemaObjectKey", "validate_current_database_schema")


@dataclass(frozen=True, slots=True, order=True)
class SchemaObjectKey:
    object_type: str
    name: str


def _read_schema_objects(conn: sqlite3.Connection) -> dict[SchemaObjectKey, str]:
    rows = conn.execute(
        """
        SELECT type, name, sql
        FROM sqlite_schema
        WHERE type IN ('index', 'table', 'trigger', 'view')
          AND name NOT LIKE 'sqlite_%'
          AND sql IS NOT NULL
        ORDER BY type, name
        """,
    ).fetchall()
    objects: dict[SchemaObjectKey, str] = {}
    for row in rows:
        object_type = str(row[0])
        name = str(row[1])
        sql = str(row[2])
        objects[SchemaObjectKey(object_type, name)] = normalize_schema_sql(sql)
    return objects


def _expected_schema_objects(task_catalog: TaskTypeCatalog) -> dict[SchemaObjectKey, str]:
    expected = sqlite3.connect(":memory:")
    try:
        expected.execute("PRAGMA foreign_keys = ON")
        apply_current_schema_objects(expected, task_catalog)
        return _read_schema_objects(expected)
    finally:
        expected.close()


def _names(keys: set[SchemaObjectKey]) -> list[str]:
    return [f"{key.object_type}:{key.name}" for key in sorted(keys)]


def _raise_schema_mismatch(
    *,
    missing: set[SchemaObjectKey],
    extra: set[SchemaObjectKey],
    changed: set[SchemaObjectKey],
) -> None:
    raise StateError(
        "Current database schema does not match the canonical shape.",
        details={
            "missing": _names(missing),
            "extra": _names(extra),
            "changed": _names(changed),
        },
    )


def validate_current_database_schema(
    conn: sqlite3.Connection,
    task_catalog: TaskTypeCatalog,
) -> None:
    expected = _expected_schema_objects(task_catalog)
    actual = _read_schema_objects(conn)
    expected_keys = set(expected)
    actual_keys = set(actual)
    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys
    changed = {key for key in expected_keys & actual_keys if expected[key] != actual[key]}
    if missing or extra or changed:
        _raise_schema_mismatch(missing=missing, extra=extra, changed=changed)
    validate_current_webui_identity_rows(conn)
