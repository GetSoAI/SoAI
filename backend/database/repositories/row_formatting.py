"""SoAI - Database repository row formatting utilities [backend/database/repositories/row_formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.security.encryption import decrypt_data
from database.core.row_materialization import format_sqlite_row

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "format_api_key_field",
    "format_row",
)

API_KEY_MASK = "********"


def format_row(row: Mapping[str, SQLiteValue] | None) -> JSONDict | None:
    return format_sqlite_row(row)


def format_api_key_field(
    row: JSONDict,
    fernet: Sequence[Fernet],
    *,
    encrypted_column: str,
    output_key: str = "api_key",
    decrypt_key: bool = False,
) -> None:
    encrypted_value_raw = row.get(encrypted_column)
    encrypted_value = encrypted_value_raw if isinstance(encrypted_value_raw, str) else None
    if decrypt_key:
        row[output_key] = decrypt_data(fernet, encrypted_value)
    else:
        row[output_key] = API_KEY_MASK if encrypted_value else None
