"""SoAI - Repository owner scoping normalization helpers [backend/database/repositories/owner_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from database.core.storage_fields import (
    normalize_optional_api_key_id,
    normalize_optional_user_id,
    read_stored_optional_api_key_id,
    read_stored_optional_user_id,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "OwnerScope",
    "normalize_owner_scope",
    "read_stored_owner_scope",
)


@dataclass(frozen=True, slots=True)
class OwnerScope:
    user_id: int | None
    api_key_id: str | None


def normalize_owner_scope(*, user_id: int | None, api_key_id: str | None) -> OwnerScope:
    return OwnerScope(
        user_id=normalize_optional_user_id(user_id),
        api_key_id=normalize_optional_api_key_id(api_key_id),
    )


def _read_stored_value(
    row: Mapping[str, SQLiteValue],
    key: str,
    *,
    error_message: str,
) -> SQLiteValue:
    if key not in row:
        raise ValidationError(error_message)
    return row[key]


def read_stored_owner_scope(
    row: Mapping[str, SQLiteValue],
    *,
    user_id_key: str,
    token_id_key: str,
    error_message: str,
) -> OwnerScope:
    return OwnerScope(
        user_id=read_stored_optional_user_id(
            _read_stored_value(row, user_id_key, error_message=error_message),
            error_message=error_message,
        ),
        api_key_id=read_stored_optional_api_key_id(
            _read_stored_value(row, token_id_key, error_message=error_message),
            error_message=error_message,
        ),
    )
