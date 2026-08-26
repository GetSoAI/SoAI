"""SoAI - Database migration step registry [backend/database/migrations/registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

    from core.logging.protocols import LoggerProtocol

__all__ = (
    "DATABASE_MIGRATION_STEPS",
    "DatabaseMigrationStep",
)


@dataclass(frozen=True, slots=True)
class DatabaseMigrationStep:
    from_version: int
    to_version: int
    apply: Callable[[sqlite3.Connection, LoggerProtocol], None]


DATABASE_MIGRATION_STEPS: tuple[DatabaseMigrationStep, ...] = ()
