"""SoAI - Database live metrics operations [backend/database/repositories/metrics/live.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from database.core.query_execution import query_to_dicts
from database.core.row_materialization import sqlite_row_dicts_to_json_dicts

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_all_live_metrics_query",
    "sync_clear_all_live_metrics",
    "sync_upsert_live_metrics",
)


def sync_upsert_live_metrics(
    conn: sqlite3.Connection,
    metrics: list[tuple[str, str, int]],
) -> None:
    conn.execute("DELETE FROM metrics_live")
    if metrics:
        conn.executemany(
            "INSERT INTO metrics_live (metric_key, value, updated_at_ms) VALUES (?, ?, ?)",
            metrics,
        )


async def get_all_live_metrics_query(
    database: aiosqlite.Connection,
) -> list[JSONDict]:
    rows = await query_to_dicts(database, "SELECT * FROM metrics_live")
    return sqlite_row_dicts_to_json_dicts(rows)


def sync_clear_all_live_metrics(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM metrics_live")
