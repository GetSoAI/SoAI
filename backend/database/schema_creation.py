"""SoAI - Database schema creation primitives [backend/database/schema_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.notifications.notification_contracts import (
    validate_notifications_sql_contract,
)
from core.tasks.type_catalog import TaskTypeCatalog
from database.application_identity import enforce_database_application_id
from database.core.savepoints import SQLiteSavepoint
from database.current_schema_objects import apply_current_schema_objects
from database.current_schema_validation import validate_current_database_schema
from database.schema_version import (
    CURRENT_DATABASE_SCHEMA_VERSION,
    ensure_supported_database_schema_version,
    read_database_schema_version,
    write_current_database_schema_version,
)
from database.task_status_sql_contract import validate_task_status_sql_contract

__all__ = ("sync_create_database_schema",)


def _database_has_application_objects(conn: sqlite3.Connection) -> bool:
    cursor = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        LIMIT 1
        """,
    )
    return cursor.fetchone() is not None


def sync_create_database_schema(
    conn: sqlite3.Connection,
    task_catalog: TaskTypeCatalog,
) -> None:
    schema_version = read_database_schema_version(conn)
    ensure_supported_database_schema_version(schema_version)
    has_application_objects = _database_has_application_objects(conn)
    fresh_database = schema_version == 0 and not has_application_objects
    if schema_version == 0 and has_application_objects:
        raise StateError(
            "Refusing to create the SoAI schema over an existing unversioned database."
        )
    validate_task_status_sql_contract()
    validate_notifications_sql_contract()
    if fresh_database:
        with SQLiteSavepoint(conn, "create_current_schema"):
            enforce_database_application_id(conn, fresh_database=True)
            apply_current_schema_objects(conn, task_catalog)
            write_current_database_schema_version(conn)
            validate_current_database_schema(conn, task_catalog)
        return
    enforce_database_application_id(conn, fresh_database=False)
    if schema_version == CURRENT_DATABASE_SCHEMA_VERSION:
        validate_current_database_schema(conn, task_catalog)
        return
    if schema_version < CURRENT_DATABASE_SCHEMA_VERSION:
        raise StateError("Existing database schema is not current.")
