"""SoAI - Database row boolean normalization [backend/database/core/row_booleans.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.booleans import parse_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "coerce_row_bool_or_default",
    "coerce_sqlite_bool_int",
    "normalize_bool_field",
)


def coerce_row_bool_or_default(value: JSONValue, *, default: bool = False) -> bool:
    try:
        parsed = parse_bool(value, default=default)
    except ValidationError:
        return default
    return bool(parsed)


def coerce_sqlite_bool_int(value: JSONValue, *, default: bool) -> int:
    return int(coerce_row_bool_or_default(value, default=default))


def normalize_bool_field(row: JSONDict, key: str) -> None:
    value = row.get(key)
    if isinstance(value, bool):
        return
    if value == 0:
        row[key] = False
        return
    if value == 1:
        row[key] = True
