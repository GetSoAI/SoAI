"""SoAI - Shared metrics history row fetching logic [backend/database/repositories/metrics/history/rows_fetch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from database.core.query_execution import query_to_dicts
from database.repositories.metrics.history.metric_key_validation import (
    require_metric_key_exists,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "build_history_query_params",
    "fetch_history_rows",
    "fetch_metric_history_rows",
)


async def fetch_history_rows(
    database: aiosqlite.Connection,
    sql: str,
    *,
    params: tuple[int | float | str | bytes | None, ...],
    metric_key: str,
) -> list[SQLiteRowDict] | None:
    rows = await query_to_dicts(database, sql, params)
    if rows:
        return rows
    await require_metric_key_exists(database, metric_key)
    return None


async def fetch_metric_history_rows(
    database: aiosqlite.Connection,
    sql: str,
    *,
    anchor_ts_ms: int,
    sanitized_interval_ms: int,
    metric_key: str,
    start_ts_ms: int,
    end_ts_ms: int,
    limit: int,
) -> list[SQLiteRowDict] | None:
    return await fetch_history_rows(
        database,
        sql,
        params=build_history_query_params(
            anchor_ts_ms,
            sanitized_interval_ms,
            metric_key,
            start_ts_ms,
            end_ts_ms,
            limit,
        ),
        metric_key=metric_key,
    )


def build_history_query_params(
    anchor_ts_ms: int,
    sanitized_interval_ms: int,
    metric_key: str,
    start_ts_ms: int,
    end_ts_ms: int,
    limit: int,
) -> tuple[int, int, int, int, str, int, int, int]:
    return (
        anchor_ts_ms,
        anchor_ts_ms,
        sanitized_interval_ms,
        sanitized_interval_ms,
        metric_key,
        start_ts_ms,
        end_ts_ms,
        limit,
    )
