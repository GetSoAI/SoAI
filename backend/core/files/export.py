"""SoAI - Core CSV export helpers [backend/core/files/export.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from typing import TYPE_CHECKING
from urllib.parse import quote

import aiosqlite

from core.errors.exceptions import ValidationError
from core.files.protocols_export import ExportDatabaseWithCoreProtocol
from core.sqlite.aiosqlite_cleanup import wait_for_aiosqlite_cleanup
from core.timing.formatting import utc_now_iso_filename_safe

if TYPE_CHECKING:
    from core.database.protocols import DatabaseReaderProtocol
    from core.types.json import JSONPrimitive

    type SQLParam = str | int | float | bytes | None
    type SQLiteValue = str | int | float | bytes | None
    type CSVValue = JSONPrimitive | bytes
    type CSVRow = Mapping[str, CSVValue]

__all__ = (
    "append_keyset_pagination_conditions",
    "build_content_disposition_attachment",
    "build_content_disposition_inline",
    "build_export_timestamp_conditions",
    "build_keyset_paginated_export_query",
    "build_keyset_pagination_clause",
    "build_timestamped_export_filename",
    "fetch_rows_as_dicts",
    "iter_csv_bytes",
    "iter_export_csv_bytes",
    "iter_keyset_paginated_rows_as_dicts",
    "require_export_database_core",
    "validate_export_time_window",
)


def require_export_database_core[CoreT](
    database: ExportDatabaseWithCoreProtocol[CoreT] | None,
    *,
    label: str,
) -> CoreT:
    if not label:
        raise ValidationError("label is required")
    if database is None:
        raise ValidationError(f"{label} with .core is required")
    try:
        core = database.core
    except AttributeError as exception:
        raise ValidationError(f"{label} with .core is required") from exception
    if core is None:
        raise ValidationError(f"{label} with .core is required")
    return core


def build_timestamped_export_filename(prefix: str, *, suffix: str = "csv") -> str:
    if not prefix:
        raise ValidationError("prefix is required")
    timestamp = utc_now_iso_filename_safe()
    return f"{prefix}-{timestamp}.{suffix}"


def _build_content_disposition(disposition: str, filename: str) -> str:
    if not disposition:
        raise ValidationError("disposition is required")
    if not filename:
        raise ValidationError("filename is required")
    if "\r" in filename or "\n" in filename:
        raise ValidationError("filename must not contain CR/LF characters")
    sanitized = filename.replace('"', "")
    if not sanitized:
        raise ValidationError("filename is invalid after sanitization")
    utf8_filename = quote(sanitized, safe="")
    return f"{disposition}; filename=\"{sanitized}\"; filename*=UTF-8''{utf8_filename}"


def build_content_disposition_attachment(filename: str) -> str:
    return _build_content_disposition("attachment", filename)


def build_content_disposition_inline(filename: str) -> str:
    return _build_content_disposition("inline", filename)


def validate_export_time_window(
    *,
    page_size: int,
    start_ts_ms: int | None,
    end_ts_ms: int | None,
) -> None:
    if page_size <= 0:
        raise ValidationError("page_size must be positive")
    if start_ts_ms is not None and isinstance(start_ts_ms, bool):
        raise ValidationError("start_ts_ms must be an integer timestamp")
    if end_ts_ms is not None and isinstance(end_ts_ms, bool):
        raise ValidationError("end_ts_ms must be an integer timestamp")
    if start_ts_ms is not None and start_ts_ms < 0:
        raise ValidationError("start_ts_ms must be non-negative")
    if end_ts_ms is not None and end_ts_ms < 0:
        raise ValidationError("end_ts_ms must be non-negative")
    if start_ts_ms is not None and end_ts_ms is not None and start_ts_ms > end_ts_ms:
        raise ValidationError("start_ts_ms must be less than or equal to end_ts_ms")


def build_export_timestamp_conditions(
    *,
    start_ts_ms: int | None,
    end_ts_ms: int | None,
) -> tuple[list[str], list[SQLParam]]:
    conditions: list[str] = []
    params_list: list[SQLParam] = []
    if start_ts_ms is not None:
        conditions.append("timestamp >= ?")
        params_list.append(start_ts_ms)
    if end_ts_ms is not None:
        conditions.append("timestamp <= ?")
        params_list.append(end_ts_ms)
    return conditions, params_list


async def iter_csv_bytes(
    *,
    fieldnames: Sequence[str],
    rows: AsyncIterator[CSVRow],
    flush_threshold_bytes: int = 65536,
) -> AsyncIterator[bytes]:
    if not fieldnames:
        raise ValidationError("fieldnames must not be empty")
    if flush_threshold_bytes < 1024:
        raise ValidationError("flush_threshold_bytes must be at least 1024")

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fieldnames), extrasaction="ignore")
    writer.writeheader()
    yield buffer.getvalue().encode("utf-8")
    buffer.seek(0)
    buffer.truncate(0)

    async for row in rows:
        writer.writerow(row)
        if buffer.tell() >= flush_threshold_bytes:
            yield buffer.getvalue().encode("utf-8")
            buffer.seek(0)
            buffer.truncate(0)

    if buffer.tell():
        yield buffer.getvalue().encode("utf-8")


def iter_export_csv_bytes(
    *,
    fieldnames: Sequence[str],
    rows: AsyncIterator[CSVRow],
    flush_threshold_bytes: int = 65536,
) -> AsyncIterator[bytes]:
    return iter_csv_bytes(
        fieldnames=fieldnames,
        rows=rows,
        flush_threshold_bytes=flush_threshold_bytes,
    )


async def fetch_rows_as_dicts(
    database: aiosqlite.Connection,
    sql: str,
    params: tuple[SQLParam, ...],
) -> list[dict[str, SQLiteValue]]:
    cursor = await database.execute(sql, params)
    try:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await wait_for_aiosqlite_cleanup(cursor.close())


def build_keyset_pagination_clause(
    *,
    key_fields: Sequence[str],
    last_key: Sequence[SQLiteValue],
) -> tuple[str, tuple[SQLParam, ...]]:
    if not key_fields:
        raise ValidationError("key_fields must not be empty")
    if len(key_fields) != len(last_key):
        raise ValidationError("key_fields and last_key must have matching lengths")
    if any(not field for field in key_fields):
        raise ValidationError("key_fields must not contain empty values")

    clauses: list[str] = []
    params: list[SQLParam] = []
    for field_index, field in enumerate(key_fields):
        prefix_conditions = [f"{prefix_field} = ?" for prefix_field in key_fields[:field_index]]
        if prefix_conditions:
            clause = f"({' AND '.join(prefix_conditions)} AND {field} > ?)"
            params.extend(list(last_key[:field_index]))
            params.append(last_key[field_index])
        else:
            clause = f"({field} > ?)"
            params.append(last_key[field_index])
        clauses.append(clause)

    return " OR ".join(clauses), tuple(params)


def append_keyset_pagination_conditions(
    *,
    conditions: list[str],
    params_list: list[SQLParam],
    key_fields: Sequence[str],
    last_key: Sequence[SQLiteValue],
) -> None:
    clause, clause_params = build_keyset_pagination_clause(key_fields=key_fields, last_key=last_key)
    conditions.append(f"({clause})")
    params_list.extend(list(clause_params))


def build_keyset_paginated_export_query(
    *,
    base_sql: str,
    order_by: str,
    conditions: list[str],
    params_list: list[SQLParam],
    key_fields: Sequence[str],
    last_key: Sequence[SQLiteValue] | None,
) -> tuple[str, tuple[SQLParam, ...]]:
    if last_key is not None:
        append_keyset_pagination_conditions(
            conditions=conditions,
            params_list=params_list,
            key_fields=key_fields,
            last_key=last_key,
        )
    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"{base_sql}{where_clause} ORDER BY {order_by} LIMIT ?"
    return (sql, tuple(params_list))


async def iter_keyset_paginated_rows_as_dicts(
    *,
    reader: DatabaseReaderProtocol,
    page_size: int,
    build_query: Callable[
        [Sequence[SQLiteValue] | None],
        tuple[str, tuple[SQLParam, ...]],
    ],
    last_key_from_row: Callable[[Mapping[str, SQLiteValue]], Sequence[SQLiteValue]],
) -> AsyncIterator[dict[str, SQLiteValue]]:
    last_key: tuple[SQLiteValue, ...] | None = None
    while True:
        sql, params = build_query(last_key)
        page = await reader.execute_read(
            fetch_rows_as_dicts,
            sql,
            (*params, page_size),
        )
        if not page:
            return
        for record in page:
            yield record
        last_key = tuple(last_key_from_row(page[-1]))
