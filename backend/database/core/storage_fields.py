"""SoAI - Shared repository storage field normalization [backend/database/core/storage_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.timing.epoch import epoch_ms
from core.users.user_id import require_strict_user_id
from core.validation.epoch import EPOCH_MS_MIN, require_unix_epoch_ms
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "normalize_optional_api_key_id",
    "normalize_optional_user_id",
    "optional_storage_text",
    "read_stored_optional_api_key_id",
    "read_stored_optional_user_id",
    "read_stored_required_text",
    "require_storage_text",
    "resolve_deleted_at_ms",
)


def require_storage_text(value: JSONValue, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string.")
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        raise ValidationError(f"{field} is required.")
    return normalized


def optional_storage_text(value: JSONValue, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string.")
    return coerce_optional_trimmed_str(value)


def normalize_optional_api_key_id(value: JSONValue) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("api_key_id must be a string or null.")
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        raise ValidationError("api_key_id must be a non-empty string.")
    return normalized


def normalize_optional_user_id(value: int | None) -> int | None:
    if value is None:
        return None
    return require_strict_user_id(value, message="user_id must be a positive integer or null.")


def read_stored_optional_user_id(value: SQLiteValue, *, error_message: str) -> int | None:
    if value is None:
        return None
    return require_strict_user_id(value, message=error_message)


def read_stored_required_text(value: SQLiteValue, *, error_message: str) -> str:
    if isinstance(value, str):
        normalized = coerce_optional_trimmed_str(value)
        if normalized is not None:
            return normalized
    raise ValidationError(error_message)


def read_stored_optional_api_key_id(value: SQLiteValue, *, error_message: str) -> str | None:
    if value is None:
        return None
    return read_stored_required_text(value, error_message=error_message)


def resolve_deleted_at_ms(value: int | None) -> int:
    if value is None:
        return int(epoch_ms())
    return require_unix_epoch_ms(
        value,
        error_message=f"deleted_at_ms must be an epoch-millisecond integer >= {EPOCH_MS_MIN}.",
        enforce_maximum=False,
    )
