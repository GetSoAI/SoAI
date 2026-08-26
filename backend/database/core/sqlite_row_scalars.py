"""SoAI - Strict SQLite row scalar extraction [backend/database/core/sqlite_row_scalars.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.types.json import JSONValue
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    type SQLiteScalarRow = Mapping[str, JSONValue | bytes]

__all__ = (
    "require_sqlite_row_bytes",
    "require_sqlite_row_int",
    "require_sqlite_row_non_empty_str",
    "require_sqlite_row_str",
    "require_sqlite_row_trimmed_non_empty_str",
    "sqlite_row_optional_bool_from_int",
    "sqlite_row_optional_int",
    "sqlite_row_optional_str",
    "sqlite_row_optional_trimmed_str",
)


def _invalid_field(label: str, field_name: str) -> StateError:
    return StateError(f"{label} {field_name} is invalid.")


def require_sqlite_row_bytes(
    row: SQLiteScalarRow,
    field_name: str,
    *,
    label: str,
) -> bytes:
    value = row.get(field_name)
    if not isinstance(value, bytes):
        raise _invalid_field(label, field_name)
    return value


def require_sqlite_row_str(row: SQLiteScalarRow, field_name: str, *, label: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str):
        raise _invalid_field(label, field_name)
    return value


def require_sqlite_row_non_empty_str(row: SQLiteScalarRow, field_name: str, *, label: str) -> str:
    value = require_sqlite_row_str(row, field_name, label=label)
    if not value.strip():
        raise _invalid_field(label, field_name)
    return value


def require_sqlite_row_trimmed_non_empty_str(
    row: SQLiteScalarRow,
    field_name: str,
    *,
    label: str,
) -> str:
    value = require_sqlite_row_str(row, field_name, label=label)
    normalized = value.strip()
    if not normalized:
        raise _invalid_field(label, field_name)
    return normalized


def sqlite_row_optional_str(row: SQLiteScalarRow, field_name: str, *, label: str) -> str | None:
    value = row.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise _invalid_field(label, field_name)
    return value


def sqlite_row_optional_trimmed_str(
    row: SQLiteScalarRow,
    field_name: str,
    *,
    label: str,
) -> str | None:
    value = sqlite_row_optional_str(row, field_name, label=label)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def require_sqlite_row_int(
    row: SQLiteScalarRow,
    field_name: str,
    *,
    label: str,
    minimum: int | None = 0,
) -> int:
    value = row.get(field_name)
    if not is_strict_int(value):
        raise _invalid_field(label, field_name)
    if minimum is not None and value < minimum:
        raise _invalid_field(label, field_name)
    return value


def sqlite_row_optional_int(
    row: SQLiteScalarRow,
    field_name: str,
    *,
    label: str,
    minimum: int | None = 0,
) -> int | None:
    value = row.get(field_name)
    if value is None:
        return None
    if not is_strict_int(value):
        raise _invalid_field(label, field_name)
    if minimum is not None and value < minimum:
        raise _invalid_field(label, field_name)
    return value


def sqlite_row_optional_bool_from_int(
    row: SQLiteScalarRow,
    field_name: str,
    *,
    label: str,
) -> bool | None:
    value = row.get(field_name)
    if value is None:
        return None
    if value not in (0, 1):
        raise _invalid_field(label, field_name)
    return value == 1
