"""SoAI - Database user count queries [backend/database/repositories/users/user_count_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.database.protocols import DatabaseCoreProtocol
from core.errors.exceptions import ConflictError, StateError
from core.users.bootstrap_state import BootstrapState
from database.core.query_execution import query_to_dicts
from database.core.sqlite_numbers import coerce_non_negative_int_from_sqlite

__all__ = (
    "query_human_admin_count",
    "query_human_user_count",
    "query_bootstrap_state",
    "sync_read_bootstrap_state",
    "sync_require_uninitialized_bootstrap_state",
)


def sync_read_bootstrap_state(connection: sqlite3.Connection) -> BootstrapState:
    row = connection.execute("""SELECT
        EXISTS(
            SELECT 1 FROM webui_system_settings
            WHERE key = 'wizard_completed' AND value = '1'
        ) AS completed,
        COUNT(*) AS human_users,
        COALESCE(SUM(CASE WHEN is_admin = 1 THEN 1 ELSE 0 END), 0) AS human_admins
        FROM webui_users WHERE account_type = 'human'""").fetchone()
    if row is None:
        raise StateError("Bootstrap state query returned no result.")
    completed, human_users, human_admins = (int(value) for value in row)
    return _resolve_bootstrap_counts(completed, human_users, human_admins)


def _resolve_bootstrap_counts(
    completed: int,
    human_users: int,
    human_admins: int,
) -> BootstrapState:
    if completed not in {0, 1} or human_admins > human_users:
        raise StateError("Bootstrap state query returned inconsistent counts.")
    if completed == 0 and human_users == 0:
        return BootstrapState.UNINITIALIZED
    if completed == 1 and human_users > 0 and human_admins > 0:
        return BootstrapState.COMPLETE
    return BootstrapState.INTEGRITY_ERROR


def sync_require_uninitialized_bootstrap_state(connection: sqlite3.Connection) -> None:
    if sync_read_bootstrap_state(connection) is not BootstrapState.UNINITIALIZED:
        raise ConflictError("Initial setup is not available.")


async def _query_count(core: DatabaseCoreProtocol, query: str) -> int:
    async def _query(database: aiosqlite.Connection) -> int:
        rows = await query_to_dicts(database, query)
        if not rows:
            return 0
        return coerce_non_negative_int_from_sqlite(rows[0].get("count"))

    return await core.reader.execute_read(_query)


async def query_human_user_count(core: DatabaseCoreProtocol) -> int:
    return await _query_count(
        core,
        "SELECT COUNT(*) AS count FROM webui_users WHERE account_type = 'human'",
    )


async def query_human_admin_count(core: DatabaseCoreProtocol) -> int:
    return await _query_count(
        core,
        """
        SELECT COUNT(*) AS count
        FROM webui_users
        WHERE account_type = 'human' AND is_admin = 1
        """,
    )


async def query_bootstrap_state(core: DatabaseCoreProtocol) -> BootstrapState:
    async def _query(database: aiosqlite.Connection) -> BootstrapState:
        rows = await query_to_dicts(
            database,
            """
            SELECT
                EXISTS(
                    SELECT 1 FROM webui_system_settings
                    WHERE key = 'wizard_completed' AND value = '1'
                ) AS completed,
                COUNT(*) AS human_users,
                COALESCE(SUM(CASE WHEN is_admin = 1 THEN 1 ELSE 0 END), 0) AS human_admins
            FROM webui_users
            WHERE account_type = 'human'
            """,
        )
        if len(rows) != 1:
            raise StateError("Bootstrap state query returned an invalid result.")
        row = rows[0]
        completed = coerce_non_negative_int_from_sqlite(row.get("completed"))
        human_users = coerce_non_negative_int_from_sqlite(row.get("human_users"))
        human_admins = coerce_non_negative_int_from_sqlite(row.get("human_admins"))
        return _resolve_bootstrap_counts(completed, human_users, human_admins)

    return await core.reader.execute_read(_query)
