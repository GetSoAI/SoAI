"""SoAI - History reads with indexed sample availability bounds [backend/database/core/history_availability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING

import aiosqlite

from core.history.request.availability import HistoryAvailabilityQuery
from core.timing.durations import hours_to_ms
from core.timing.epoch import epoch_ms
from database.core.query_execution import query_one_to_dict
from database.core.read_transaction import run_read_transaction
from database.core.sql_builders import validate_sql_identifier
from database.core.sqlite_row_scalars import sqlite_row_optional_int

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = ("read_history_with_availability",)


async def read_history_with_availability(
    database: aiosqlite.Connection,
    query_history: Callable[[aiosqlite.Connection], Awaitable[JSONDict]],
    availability: HistoryAvailabilityQuery,
    *,
    table: str,
    value_column: str,
    filters: Sequence[tuple[str, SQLiteValue]],
) -> JSONDict:
    async def _transaction(connection: aiosqlite.Connection) -> JSONDict:
        history = await query_history(connection)
        metadata = history.get("metadata")
        if not isinstance(metadata, dict):
            raise TypeError("History query must return metadata as a dictionary")
        history["metadata"] = {
            **metadata,
            "availability": await _query_sample_bounds(
                connection,
                availability.retention_hours,
                table=table,
                value_column=value_column,
                filters=filters,
            ),
        }
        return history

    return await run_read_transaction(database, _transaction)


async def _query_sample_bounds(
    database: aiosqlite.Connection,
    retention_hours: int,
    *,
    table: str,
    value_column: str,
    filters: Sequence[tuple[str, SQLiteValue]],
) -> JSONDict:
    observed_at_ms = epoch_ms()
    retention_ms = hours_to_ms(retention_hours)
    table_sql = validate_sql_identifier(table, label="table")
    conditions = [
        f"{validate_sql_identifier(value_column, label='metric column')} IS NOT NULL",
        "observed_at_ms <= ?",
    ]
    params: list[SQLiteValue] = [observed_at_ms]
    if retention_ms > 0:
        conditions.append("observed_at_ms >= ?")
        params.append(observed_at_ms - retention_ms)
    for column, value in filters:
        conditions.append(f"{validate_sql_identifier(column, label='filter column')} = ?")
        params.append(value)
    where_sql = " AND ".join(conditions)
    row = (
        await query_one_to_dict(
            database,
            (
                f"SELECT (SELECT observed_at_ms FROM {table_sql} WHERE {where_sql} "
                "ORDER BY observed_at_ms ASC LIMIT 1) AS oldest_sample_ts_ms, "
                f"(SELECT observed_at_ms FROM {table_sql} WHERE {where_sql} "
                "ORDER BY observed_at_ms DESC LIMIT 1) AS newest_sample_ts_ms"
            ),
            (*params, *params),
        )
        or {}
    )
    label = f"{table_sql} availability"
    return {
        "oldest_sample_ts_ms": sqlite_row_optional_int(row, "oldest_sample_ts_ms", label=label),
        "newest_sample_ts_ms": sqlite_row_optional_int(row, "newest_sample_ts_ms", label=label),
        "observed_at_ms": observed_at_ms,
    }
