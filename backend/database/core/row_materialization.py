"""SoAI - SQLite row materialization helpers [backend/database/core/row_materialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import DatabaseError, ValidationError
from core.types.json_value import is_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRowDict, SQLiteValue

__all__ = (
    "coerce_sqlite_row_dict_to_json_dict",
    "format_sqlite_row",
    "sqlite_row_dict_to_json_dict",
    "sqlite_row_dicts_to_json_dicts",
)


def format_sqlite_row(row: Mapping[str, SQLiteValue] | None) -> JSONDict | None:
    if not row:
        return None
    result: JSONDict = {}
    for key, value in row.items():
        if not isinstance(key, str):
            continue
        result[key] = _coerce_json_value(value)
    return result


def sqlite_row_dict_to_json_dict(row: SQLiteRowDict) -> JSONDict:
    converted: JSONDict = {}
    for key, value in row.items():
        if isinstance(value, bytes):
            raise ValidationError(
                "SQLite row contains bytes which cannot be represented as JSON.",
                details={"key": key},
            )
        converted[key] = value
    return converted


def sqlite_row_dicts_to_json_dicts(rows: Iterable[SQLiteRowDict]) -> list[JSONDict]:
    return [sqlite_row_dict_to_json_dict(row) for row in rows]


def coerce_sqlite_row_dict_to_json_dict(
    row: SQLiteRowDict,
    *,
    invalid_utf8_message: str,
    operation: str,
) -> JSONDict:
    coerced: JSONDict = {}
    for key, value in row.items():
        if isinstance(value, bytes):
            try:
                coerced[key] = value.decode("utf-8")
            except UnicodeDecodeError as exception:
                raise DatabaseError(
                    invalid_utf8_message,
                    operation=operation,
                ) from exception
            continue
        coerced[key] = value
    return coerced


def _coerce_json_value(value: SQLiteValue) -> JSONValue:
    if is_json_value(value):
        return value
    if isinstance(value, bytes | bytearray):
        return value.decode("utf-8", errors="backslashreplace")
    return str(value)
