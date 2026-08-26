"""SoAI - Metrics history row mapping utilities [backend/database/repositories/metrics/history/row_mapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from database.core.sqlite_numbers import coerce_int_from_sqlite

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("build_row_map_by_timestamp",)


def build_row_map_by_timestamp(rows: list[SQLiteRowDict]) -> dict[int, SQLiteRowDict]:
    row_map: dict[int, SQLiteRowDict] = {}
    for row_entry in rows:
        if not isinstance(row_entry, dict):
            raise ValidationError("Database query returned a non-row mapping.")
        timestamp_value = row_entry.get("bin_start_ts")
        timestamp = coerce_int_from_sqlite(timestamp_value)
        if timestamp is not None:
            row_map[timestamp] = row_entry
    return row_map
