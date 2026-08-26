"""SoAI - SQLite statement builders with identifier validation [backend/database/core/sql_builders.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "build_delete_all_statement",
    "build_insert_statement",
    "build_placeholder_list",
    "build_update_statement",
    "build_upsert_statement",
    "validate_sql_identifier",
)

_IDENTIFIER_REGEX = r"^[A-Za-z_][A-Za-z0-9_]*$"


def validate_sql_identifier(value: str, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{label} must be non-empty.")
    if re.fullmatch(_IDENTIFIER_REGEX, normalized) is None:
        raise ValidationError(f"{label} is not a valid SQL identifier: '{normalized}'.")
    return normalized


def _validate_identifiers(values: Sequence[str], *, label: str) -> tuple[str, ...]:
    return tuple(validate_sql_identifier(value, label=label) for value in values)


def build_placeholder_list(count: int) -> str:
    if not is_strict_int(count) or count <= 0:
        raise ValidationError("SQL placeholder count must be a positive integer.")
    return ", ".join("?" for _ in range(count))


def build_update_statement(
    *,
    table: str,
    updates: Mapping[str, SQLiteValue],
    where_clause: str,
    where_params: Sequence[SQLiteValue] = (),
    allowed_columns: set[str] | frozenset[str] | tuple[str, ...] | None = None,
) -> tuple[str, tuple[SQLiteValue, ...]]:
    if not updates:
        raise ValidationError("updates must not be empty.")
    table_name = validate_sql_identifier(table, label="table")
    update_keys = _validate_identifiers(tuple(updates.keys()), label="column")
    if allowed_columns is not None:
        allowed_names = set(_validate_identifiers(tuple(allowed_columns), label="allowed column"))
        invalid = set(update_keys) - allowed_names
        if invalid:
            invalid_names = ", ".join(sorted(invalid))
            raise ValidationError(f"Invalid column names for update: {invalid_names}")
    ordered_keys = tuple(sorted(update_keys))
    assignments = ", ".join(f"{key} = ?" for key in ordered_keys)
    sql = f"UPDATE {table_name} SET {assignments} WHERE {where_clause}"
    params: list[SQLiteValue] = [updates[key] for key in ordered_keys]
    params.extend(list(where_params))
    return (sql, tuple(params))


def build_insert_statement(*, table: str, columns: Sequence[str]) -> str:
    if not columns:
        raise ValidationError("insert columns must not be empty.")
    table_name = validate_sql_identifier(table, label="table")
    column_names = _validate_identifiers(columns, label="column")
    columns_sql = ", ".join(column_names)
    placeholders = build_placeholder_list(len(column_names))
    return f"INSERT INTO {table_name} ({columns_sql}) VALUES ({placeholders})"


def build_upsert_statement(
    *,
    table: str,
    columns: Sequence[str],
    conflict_columns: Sequence[str],
    update_columns: Sequence[str],
) -> str:
    if not conflict_columns:
        raise ValidationError("upsert conflict columns must not be empty.")
    if not update_columns:
        raise ValidationError("upsert update columns must not be empty.")
    insert_sql = build_insert_statement(table=table, columns=columns)
    conflict_names = _validate_identifiers(conflict_columns, label="conflict column")
    update_names = _validate_identifiers(update_columns, label="update column")
    column_set = set(_validate_identifiers(columns, label="column"))
    invalid_conflicts = set(conflict_names) - column_set
    if invalid_conflicts:
        invalid_conflict_names = ", ".join(sorted(invalid_conflicts))
        raise ValidationError(f"Invalid upsert conflict columns: {invalid_conflict_names}")
    invalid_updates = set(update_names) - column_set
    if invalid_updates:
        invalid_update_names = ", ".join(sorted(invalid_updates))
        raise ValidationError(f"Invalid upsert update columns: {invalid_update_names}")
    conflict_sql = ", ".join(conflict_names)
    assignments_sql = ", ".join(f"{column} = excluded.{column}" for column in update_names)
    return f"{insert_sql} ON CONFLICT({conflict_sql}) DO UPDATE SET {assignments_sql}"


def build_delete_all_statement(*, table: str) -> str:
    table_name = validate_sql_identifier(table, label="table")
    return f"DELETE FROM {table_name}"
