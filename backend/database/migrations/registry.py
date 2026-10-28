"""SoAI - Database migration step registry [backend/database/migrations/registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from database.migrations.schema_1_to_2 import migrate_database_schema_1_to_2
from database.migrations.schema_2_to_3 import migrate_database_schema_2_to_3
from database.migrations.schema_3_to_4 import migrate_database_schema_3_to_4

if TYPE_CHECKING:
    import sqlite3

    from core.logging.protocols import LoggerProtocol

__all__ = (
    "DatabaseMigrationStep",
    "build_database_migration_steps",
)


@dataclass(frozen=True, slots=True)
class DatabaseMigrationStep:
    from_version: int
    to_version: int
    apply: Callable[[sqlite3.Connection, LoggerProtocol], None]


def build_database_migration_steps() -> tuple[DatabaseMigrationStep, ...]:
    return (
        DatabaseMigrationStep(
            from_version=1,
            to_version=2,
            apply=migrate_database_schema_1_to_2,
        ),
        DatabaseMigrationStep(
            from_version=2,
            to_version=3,
            apply=migrate_database_schema_2_to_3,
        ),
        DatabaseMigrationStep(
            from_version=3,
            to_version=4,
            apply=migrate_database_schema_3_to_4,
        ),
    )
