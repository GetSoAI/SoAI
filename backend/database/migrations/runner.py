"""SoAI - Database schema migration runner [backend/database/migrations/runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.tasks.type_catalog import TaskTypeCatalog
from database.migrations.registry import DATABASE_MIGRATION_STEPS, DatabaseMigrationStep
from database.schema_creation import sync_create_database_schema
from database.schema_version import (
    CURRENT_DATABASE_SCHEMA_VERSION,
    ensure_supported_database_schema_version,
    read_database_schema_version,
    write_database_schema_version,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = ("upgrade_database_schema_to_current",)


def _index_steps(
    steps: tuple[DatabaseMigrationStep, ...],
) -> dict[int, DatabaseMigrationStep]:
    indexed: dict[int, DatabaseMigrationStep] = {}
    for step in steps:
        if step.from_version in indexed:
            raise StateError(
                f"Duplicate database migration step for from_version: {step.from_version} -> {indexed[step.from_version].to_version} and {step.to_version}.",
            )
        if step.to_version <= step.from_version:
            raise StateError(
                f"Invalid database migration step: from_version={step.from_version} to_version={step.to_version}.",
            )
        indexed[step.from_version] = step
    return indexed


def upgrade_database_schema_to_current(
    conn: sqlite3.Connection,
    *,
    logger: LoggerProtocol,
    task_catalog: TaskTypeCatalog,
) -> tuple[int, int]:
    from_version = read_database_schema_version(conn)
    ensure_supported_database_schema_version(from_version)
    if from_version == 0:
        sync_create_database_schema(conn, task_catalog)
        return (from_version, CURRENT_DATABASE_SCHEMA_VERSION)
    if from_version == CURRENT_DATABASE_SCHEMA_VERSION:
        sync_create_database_schema(conn, task_catalog)
        return (from_version, CURRENT_DATABASE_SCHEMA_VERSION)

    indexed = _index_steps(DATABASE_MIGRATION_STEPS)
    working_version = from_version
    while working_version < CURRENT_DATABASE_SCHEMA_VERSION:
        step = indexed.get(working_version)
        if step is None:
            raise StateError(
                f"Missing database migration step: from_version={working_version} to_version={CURRENT_DATABASE_SCHEMA_VERSION}.",
            )
        logger.warning(
            "Database migration: applying step %s -> %s",
            step.from_version,
            step.to_version,
        )
        step.apply(conn, logger)
        write_database_schema_version(conn, step.to_version)
        working_version = step.to_version

    sync_create_database_schema(conn, task_catalog)
    return (from_version, CURRENT_DATABASE_SCHEMA_VERSION)
