"""SoAI - Database schema migration from 2 to 3 [backend/database/migrations/schema_2_to_3.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from database.schema_scripts.plugin_backend_updates import PLUGIN_BACKEND_UPDATES_SCHEMA_V3
from database.sql.script import execute_sql_script

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol


__all__ = ("migrate_database_schema_2_to_3",)


def migrate_database_schema_2_to_3(
    connection: sqlite3.Connection,
    logger: LoggerProtocol,
) -> None:
    del logger
    connection.execute(
        """ALTER TABLE unified_tasks ADD COLUMN public_error_message TEXT
        CHECK(public_error_message IS NULL OR (status = 'failed' AND length(trim(public_error_message)) > 0))"""
    )
    execute_sql_script(connection, PLUGIN_BACKEND_UPDATES_SCHEMA_V3)
