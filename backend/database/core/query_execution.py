"""SoAI - Database query execution helpers [backend/database/core/query_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.sqlite.aiosqlite_cleanup import wait_for_aiosqlite_cleanup
from database.core.row_materialization import sqlite_row_dicts_to_json_dicts

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict, SQLiteValue

__all__ = (
    "query_one_to_dict",
    "query_to_dicts",
    "sync_fetch_all_as_dicts",
    "sync_fetch_all_as_json_dicts",
    "sync_fetch_all_first_column",
    "sync_fetch_changes_count",
    "sync_fetch_one_as_dict",
    "sync_fetch_one_scalar",
)

LOGGER_NAME = "SoAI.database.core.query_execution"
OPERATION_DATABASE_QUERY_CLOSE_CURSOR = "database.query_helpers.close_cursor"
OPERATION_DATABASE_QUERY_CLOSE_SYNC_CURSOR = "database.query_helpers.close_sync_cursor"
QUERY_FETCH_BATCH_SIZE = 512
ASYNC_CURSOR_CLOSE_EXCEPTIONS: tuple[type[Exception], ...] = (
    aiosqlite.Error,
    *RECOVERABLE_EXCEPTIONS,
)
SYNC_CURSOR_CLOSE_EXCEPTIONS: tuple[type[Exception], ...] = (
    sqlite3.Error,
    *RECOVERABLE_EXCEPTIONS,
)


async def query_to_dicts(
    database: aiosqlite.Connection,
    sql: str,
    params: tuple[SQLiteValue, ...] = (),
) -> list[SQLiteRowDict]:
    cursor = await database.execute(sql, params)
    try:
        rows: list[SQLiteRowDict] = []
        while True:
            batch = tuple(await cursor.fetchmany(QUERY_FETCH_BATCH_SIZE))
            if not batch:
                return rows
            for row in batch:
                rows.append(dict(row))
    finally:
        await wait_for_aiosqlite_cleanup(_close_cursor(cursor))


async def query_one_to_dict(
    database: aiosqlite.Connection,
    sql: str,
    params: tuple[SQLiteValue, ...] = (),
) -> SQLiteRowDict | None:
    cursor = await database.execute(sql, params)
    try:
        row = await cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        await wait_for_aiosqlite_cleanup(_close_cursor(cursor))


def sync_fetch_all_as_dicts(cursor: sqlite3.Cursor) -> list[SQLiteRowDict]:
    try:
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        _close_sync_cursor(cursor)


def sync_fetch_all_first_column(cursor: sqlite3.Cursor) -> list[SQLiteValue]:
    try:
        rows = cursor.fetchall()
        values: list[SQLiteValue] = []
        for row in rows:
            if row is None or len(row) < 1:
                continue
            value = row[0]
            if isinstance(value, int | float | str | bytes) or value is None:
                values.append(value)
        return values
    finally:
        _close_sync_cursor(cursor)


def sync_fetch_all_as_json_dicts(cursor: sqlite3.Cursor) -> list[JSONDict]:
    return sqlite_row_dicts_to_json_dicts(sync_fetch_all_as_dicts(cursor))


def sync_fetch_one_as_dict(cursor: sqlite3.Cursor) -> SQLiteRowDict | None:
    try:
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        _close_sync_cursor(cursor)


def sync_fetch_one_scalar(cursor: sqlite3.Cursor) -> SQLiteValue | None:
    try:
        row = cursor.fetchone()
        if row is None or len(row) < 1:
            return None
        value = row[0]
        if isinstance(value, int | float | str | bytes) or value is None:
            return value
        return None
    finally:
        _close_sync_cursor(cursor)


def sync_fetch_changes_count(connection: sqlite3.Connection) -> int:
    cursor = connection.execute("SELECT changes()")
    try:
        row = cursor.fetchone()
    finally:
        _close_sync_cursor(cursor)
    try:
        return _require_changes_count(row)
    except (TypeError, ValueError, OverflowError) as exception:
        raise sqlite3.DatabaseError("SELECT changes() returned an invalid result.") from exception


def _require_changes_count(row: tuple[SQLiteValue, ...] | sqlite3.Row | None) -> int:
    if row is None or not isinstance(row, tuple | sqlite3.Row) or len(row) != 1:
        raise TypeError("SELECT changes() must return exactly one result cell.")
    value = row[0]
    if isinstance(value, bool):
        raise TypeError("SELECT changes() must return an integer count.")
    if isinstance(value, int):
        count = value
    elif isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError("SELECT changes() must return a finite integral count.")
        count = int(value)
    elif isinstance(value, str):
        count = int(value)
    else:
        raise TypeError("SELECT changes() returned an unsupported value type.")
    if count < 0:
        raise ValueError("SELECT changes() must return a non-negative count.")
    return count


async def _close_cursor(cursor: aiosqlite.Cursor) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        await wait_for_aiosqlite_cleanup(cursor.close())
    except ASYNC_CURSOR_CLOSE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to close database cursor (non-critical).",
            operation=OPERATION_DATABASE_QUERY_CLOSE_CURSOR,
            level="debug",
        )


def _close_sync_cursor(cursor: sqlite3.Cursor) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        cursor.close()
    except SYNC_CURSOR_CLOSE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to close database cursor (non-critical).",
            operation=OPERATION_DATABASE_QUERY_CLOSE_SYNC_CURSOR,
            level="debug",
        )
