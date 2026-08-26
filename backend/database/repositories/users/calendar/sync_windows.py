"""SoAI - Calendar sync window repository operations [backend/database/repositories/users/calendar/sync_windows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.users.account_identifier_validation import require_calendar_calendar_id
from database.core.query_execution import query_to_dicts
from database.core.sql_builders import build_upsert_statement
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.account_validation import require_epoch_ms

__all__ = (
    "read_calendar_sync_windows",
    "sync_replace_calendar_sync_window",
)


async def read_calendar_sync_windows(
    database: aiosqlite.Connection,
    *,
    calendar_id: str,
) -> list[SQLiteRowDict]:
    return await query_to_dicts(
        database,
        """
        SELECT *
        FROM calendar_sync_windows
        WHERE calendar_id = ?
        ORDER BY window_start_ms ASC, window_end_ms ASC
        """,
        (require_calendar_calendar_id(calendar_id),),
    )


def sync_replace_calendar_sync_window(
    conn: sqlite3.Connection,
    /,
    calendar_id: str,
    window_start_ms: int,
    window_end_ms: int,
    synced_at_ms: int,
) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute(
            build_upsert_statement(
                table="calendar_sync_windows",
                columns=(
                    "calendar_id",
                    "window_start_ms",
                    "window_end_ms",
                    "synced_at_ms",
                    "synced_window_start_ms",
                    "synced_window_end_ms",
                ),
                conflict_columns=("calendar_id", "window_start_ms", "window_end_ms"),
                update_columns=(
                    "synced_at_ms",
                    "synced_window_start_ms",
                    "synced_window_end_ms",
                ),
            ),
            (
                require_calendar_calendar_id(calendar_id),
                require_epoch_ms(window_start_ms, "window_start_ms"),
                require_epoch_ms(window_end_ms, "window_end_ms"),
                require_epoch_ms(synced_at_ms, "synced_at_ms"),
                require_epoch_ms(window_start_ms, "window_start_ms"),
                require_epoch_ms(window_end_ms, "window_end_ms"),
            ),
        )
    finally:
        cursor.close()
