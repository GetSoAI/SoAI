"""SoAI - SQLite value typing for repository boundaries [backend/database/core/sqlite_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    type SQLiteValue = int | float | str | bytes | None
    type SQLiteRow = Mapping[str, SQLiteValue]
    type SQLiteRowDict = dict[str, SQLiteValue]
else:
    SQLiteValue = int | float | str | bytes | None
    SQLiteRow = Mapping[str, SQLiteValue]
    SQLiteRowDict = dict[str, SQLiteValue]

__all__ = ()
