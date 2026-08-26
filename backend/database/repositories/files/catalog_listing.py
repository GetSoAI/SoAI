"""SoAI - Database file catalog listing operations [backend/database/repositories/files/catalog_listing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from core.errors.exceptions import ValidationError
from core.files.database_types import FileCatalogListPage
from core.openai.file_list_limits import (
    OPENAI_FILE_LIST_DEFAULT_LIMIT,
    OPENAI_FILE_LIST_MAX_LIMIT,
)
from core.sqlite.aiosqlite_cleanup import wait_for_aiosqlite_cleanup
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import require_positive_int_strict
from core.validation.strings import coerce_optional_trimmed_str
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.core.sqlite_values import SQLiteValue
from database.repositories.files.record_parsing import parse_file_catalog_record
from database.repositories.owner_scope import normalize_owner_scope

__all__ = ("list_files_query",)


@dataclass(slots=True)
class FileListSqlFilters:
    clauses: list[str]
    params: list[SQLiteValue]


async def list_files_query(
    database: aiosqlite.Connection,
    *,
    enforce_owner: bool = False,
    user_id: int | None = None,
    api_key_id: str | None = None,
    purpose: str | None = None,
    after: str | None = None,
    limit: int = OPENAI_FILE_LIST_DEFAULT_LIMIT,
    order: str = "desc",
) -> FileCatalogListPage:
    scope = normalize_owner_scope(user_id=user_id, api_key_id=api_key_id)
    normalized_purpose = coerce_optional_trimmed_str(purpose)
    normalized_after = coerce_optional_trimmed_str(after)
    normalized_order = _normalize_file_list_order(order)
    resolved_limit = require_positive_int_strict(
        limit,
        error_message="limit must be a positive integer.",
    )
    if resolved_limit > OPENAI_FILE_LIST_MAX_LIMIT:
        raise ValidationError(f"limit must be <= {OPENAI_FILE_LIST_MAX_LIMIT}.")
    filters = _build_file_list_filters(
        enforce_owner=enforce_owner,
        user_id=scope.user_id,
        api_key_id=scope.api_key_id,
        purpose=normalized_purpose,
    )
    began = False
    committed = False
    rows: list[dict[str, SQLiteValue]] = []
    if normalized_after is not None:
        await database.execute("BEGIN")
        began = True
    try:
        if normalized_after is not None:
            cursor = await _fetch_file_list_cursor(
                database,
                file_id=normalized_after,
                filters=filters,
            )
            if cursor is None:
                await database.execute("COMMIT")
                committed = True
                return FileCatalogListPage(records=[], has_more=False, invalid_after=True)
            _append_file_list_cursor_clause(
                filters,
                order=normalized_order,
                cursor_id=normalized_after,
                cursor_created_at=_read_cursor_created_at(cursor),
            )
        rows = await _query_file_list_rows(
            database,
            filters=filters,
            order=normalized_order,
            fetch_limit=resolved_limit + 1,
        )
        if began:
            await database.execute("COMMIT")
            committed = True
    finally:
        if began and not committed:
            await wait_for_aiosqlite_cleanup(database.execute("ROLLBACK"))
    records = [parse_file_catalog_record(row) for row in rows[:resolved_limit]]
    return FileCatalogListPage(records=records, has_more=len(rows) > resolved_limit)


async def _query_file_list_rows(
    database: aiosqlite.Connection,
    *,
    filters: FileListSqlFilters,
    order: str,
    fetch_limit: int,
) -> list[dict[str, SQLiteValue]]:
    sql = """
        SELECT id, filename, purpose, size_bytes, content_sha256, created_at_ms, user_id, api_key_id, status, status_details
        FROM files_catalog
    """
    sql += _build_file_list_where_sql(filters.clauses)
    sql += _build_file_list_order_sql(order)
    params = [*filters.params, fetch_limit]
    return await query_to_dicts(
        database,
        sql,
        tuple(params),
    )


def _normalize_file_list_order(order: str) -> str:
    normalized = str(order).strip().lower()
    if normalized in {"asc", "desc"}:
        return normalized
    raise ValidationError("order must be 'asc' or 'desc'.")


def _build_file_list_filters(
    *,
    enforce_owner: bool,
    user_id: int | None,
    api_key_id: str | None,
    purpose: str | None,
) -> FileListSqlFilters:
    clauses: list[str] = []
    params: list[SQLiteValue] = []
    if enforce_owner:
        clauses.append("user_id IS ?")
        clauses.append("api_key_id IS ?")
        params.extend((user_id, api_key_id))
    if purpose is not None:
        clauses.append("purpose = ?")
        params.append(purpose)
    return FileListSqlFilters(clauses=clauses, params=params)


async def _fetch_file_list_cursor(
    database: aiosqlite.Connection,
    *,
    file_id: str,
    filters: FileListSqlFilters,
) -> dict[str, SQLiteValue] | None:
    sql = """
        SELECT id, created_at_ms
        FROM files_catalog
    """
    clauses = ["id = ?", *filters.clauses]
    params: list[SQLiteValue] = [file_id, *filters.params]
    sql += _build_file_list_where_sql(clauses)
    return await query_one_to_dict(database, sql, tuple(params))


def _append_file_list_cursor_clause(
    filters: FileListSqlFilters,
    *,
    order: str,
    cursor_id: str,
    cursor_created_at: int,
) -> None:
    if order == "desc":
        filters.clauses.append("(created_at_ms < ? OR (created_at_ms = ? AND id < ?))")
    else:
        filters.clauses.append("(created_at_ms > ? OR (created_at_ms = ? AND id > ?))")
    filters.params.extend((cursor_created_at, cursor_created_at, cursor_id))


def _read_cursor_created_at(row: dict[str, SQLiteValue]) -> int:
    value = row.get("created_at_ms")
    if not is_strict_int(value):
        raise ValidationError("File list cursor has an invalid created_at_ms value.")
    return value


def _build_file_list_where_sql(clauses: list[str]) -> str:
    if not clauses:
        return ""
    joined = "\n          AND ".join(clauses)
    return f"\n        WHERE {joined}"


def _build_file_list_order_sql(order: str) -> str:
    if order == "asc":
        return "\n        ORDER BY created_at_ms ASC, id ASC\n        LIMIT ?"
    return "\n        ORDER BY created_at_ms DESC, id DESC\n        LIMIT ?"
