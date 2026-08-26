"""SoAI - Database schema upgrade entrypoint for updater hooks [backend/database/migrations/runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os

from core.bootstrap.lock import acquire_interprocess_lock
from core.errors.exceptions import ValidationError
from core.sqlite.connections import connect_sqlite
from core.sqlite.file_permissions import secure_sqlite_file_permissions
from core.sqlite.policy import (
    SQLITE_WRITE_PRAGMAS,
    configure_sqlite_connection,
    resolve_sqlite_database_target,
)
from core.tasks.type_catalog import TaskTypeCatalog
from database.migrations.runner import upgrade_database_schema_to_current
from database.schema_version import CURRENT_DATABASE_SCHEMA_VERSION

__all__ = ("upgrade_database_path",)


def upgrade_database_path(
    *,
    db_path: str,
    lock_path: str,
    logger: logging.Logger,
    task_catalog: TaskTypeCatalog,
) -> tuple[int, int]:
    if not db_path.strip():
        raise ValidationError("db_path must be a non-empty string.")
    if not lock_path.strip():
        raise ValidationError("lock_path must be a non-empty string.")
    with acquire_interprocess_lock(lock_path, timeout_sec=60.0):
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        secure_sqlite_file_permissions(db_path, create_missing=True)
        database_target, use_uri = resolve_sqlite_database_target(
            db_path,
            is_shared_memory_mode=False,
            read_only=False,
        )
        connection = connect_sqlite(
            database_target,
            timeout=60.0,
            isolation_level="DEFERRED",
            uri=use_uri,
        )
        try:
            configure_sqlite_connection(connection, SQLITE_WRITE_PRAGMAS)
            from_version, _ = upgrade_database_schema_to_current(
                connection,
                logger=logger,
                task_catalog=task_catalog,
            )
            connection.commit()
        finally:
            connection.close()
            secure_sqlite_file_permissions(db_path)
    return (from_version, CURRENT_DATABASE_SCHEMA_VERSION)
