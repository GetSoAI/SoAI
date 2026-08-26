"""SoAI - Shared user account storage helpers [backend/database/repositories/users/domain_account_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Callable

import aiosqlite

from core.errors.exceptions import DatabaseError, ValidationError
from core.users.user_id import require_strict_user_id
from database.core.query_execution import (
    query_one_to_dict,
    query_to_dicts,
    sync_fetch_one_as_dict,
)
from database.core.sql_builders import (
    build_insert_statement,
    build_update_statement,
    validate_sql_identifier,
)
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.core.sqlite_values import SQLiteRowDict, SQLiteValue

__all__ = (
    "delete_user_account_row",
    "insert_user_account_row",
    "read_user_account_row",
    "read_user_account_row_by_external_account_id",
    "read_user_account_rows",
    "update_user_account_row",
)


async def read_user_account_rows(
    database: aiosqlite.Connection,
    *,
    table: str,
    user_id: int,
    require_user_id: Callable[[int], int],
) -> list[SQLiteRowDict]:
    table_name = validate_sql_identifier(table, label="account table")
    return await query_to_dicts(
        database,
        f"SELECT * FROM {table_name} WHERE user_id = ? ORDER BY created_at_ms DESC, id DESC",
        (require_user_id(user_id),),
    )


async def read_user_account_row(
    database: aiosqlite.Connection,
    *,
    table: str,
    user_id: int,
    account_id: str,
    require_user_id: Callable[[int], int],
    require_account_id: Callable[[str], str],
) -> SQLiteRowDict | None:
    table_name = validate_sql_identifier(table, label="account table")
    return await query_one_to_dict(
        database,
        f"SELECT * FROM {table_name} WHERE user_id = ? AND id = ? LIMIT 1",
        (require_user_id(user_id), require_account_id(account_id)),
    )


async def read_user_account_row_by_external_account_id(
    database: aiosqlite.Connection,
    *,
    table: str,
    user_id: int,
    external_account_id: str,
    require_user_id: Callable[[int], int],
    require_external_account_id: Callable[[str], str],
) -> SQLiteRowDict | None:
    table_name = validate_sql_identifier(table, label="account table")
    return await query_one_to_dict(
        database,
        f"SELECT * FROM {table_name} WHERE user_id = ? AND external_account_id = ? LIMIT 1",
        (require_user_id(user_id), require_external_account_id(external_account_id)),
    )


def _read_inserted_or_updated_user_account_row(
    conn: sqlite3.Connection,
    *,
    table: str,
    user_id: int,
    account_id: str,
) -> SQLiteRowDict | None:
    table_name = validate_sql_identifier(table, label="account table")
    cursor = conn.execute(
        f"SELECT * FROM {table_name} WHERE user_id = ? AND id = ?",
        (user_id, account_id),
    )
    return sync_fetch_one_as_dict(cursor)


def _require_insert_row_user_id(row: SQLiteRowDict) -> int:
    try:
        return require_strict_user_id(row.get("user_id"))
    except ValidationError as exception:
        raise DatabaseError("Inserted account row payload is invalid.") from exception


def _require_insert_row_account_id(row: SQLiteRowDict) -> str:
    account_id_value = row.get("id")
    if isinstance(account_id_value, str) and account_id_value.strip():
        return account_id_value
    raise DatabaseError("Inserted account row payload is invalid.")


def insert_user_account_row(
    conn: sqlite3.Connection,
    *,
    table: str,
    row: SQLiteRowDict,
    columns: tuple[str, ...],
    create_error_message: str,
    created_read_error_message: str,
) -> SQLiteRowDict:
    cursor = conn.cursor()
    insert_sql = build_insert_statement(table=table, columns=columns)
    values = tuple(row[column] for column in columns)
    try:
        cursor.execute(insert_sql, values)
        record = _read_inserted_or_updated_user_account_row(
            conn,
            table=table,
            user_id=_require_insert_row_user_id(row),
            account_id=_require_insert_row_account_id(row),
        )
        if record is None:
            raise DatabaseError(created_read_error_message)
        return record
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        raise DatabaseError(
            create_error_message,
            details={"constraint_type": constraint_type, "detail": detail},
        ) from exception
    finally:
        cursor.close()


def update_user_account_row(
    conn: sqlite3.Connection,
    *,
    table: str,
    user_id: int,
    account_id: str,
    updates: dict[str, SQLiteValue],
    allowed_columns: set[str] | frozenset[str] | tuple[str, ...],
    require_user_id: Callable[[int], int],
    require_account_id: Callable[[str], str],
    update_error_message: str | None = None,
) -> SQLiteRowDict | None:
    normalized_user_id = require_user_id(user_id)
    normalized_account_id = require_account_id(account_id)
    sql, params = build_update_statement(
        table=table,
        updates=updates,
        where_clause="user_id = ? AND id = ?",
        where_params=(normalized_user_id, normalized_account_id),
        allowed_columns=allowed_columns,
    )
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        if cursor.rowcount <= 0:
            return None
        return _read_inserted_or_updated_user_account_row(
            conn,
            table=table,
            user_id=normalized_user_id,
            account_id=normalized_account_id,
        )
    except sqlite3.IntegrityError as exception:
        if update_error_message is None:
            raise
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        raise DatabaseError(
            update_error_message,
            details={"constraint_type": constraint_type, "detail": detail},
        ) from exception
    finally:
        cursor.close()


def delete_user_account_row(
    conn: sqlite3.Connection,
    *,
    table: str,
    user_id: int,
    account_id: str,
    require_user_id: Callable[[int], int],
    require_account_id: Callable[[str], str],
) -> bool:
    table_name = validate_sql_identifier(table, label="account table")
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"DELETE FROM {table_name} WHERE user_id = ? AND id = ?",
            (require_user_id(user_id), require_account_id(account_id)),
        )
        return cursor.rowcount > 0
    finally:
        cursor.close()
