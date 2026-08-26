"""SoAI - Shared user account repository validation helpers [backend/database/repositories/users/account_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.users.user_id import require_strict_user_id
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import is_strict_int
from core.validation.strings import require_trimmed_json_text
from database.core.json_codec import (
    serialize_optional_json_list_field,
    serialize_optional_json_object_field,
)
from database.core.row_fields import require_row_bool_int, require_row_non_negative_int

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "optional_epoch_ms",
    "optional_json_list",
    "optional_json_object",
    "require_bool_int",
    "require_epoch_ms",
    "require_nonnegative_int",
    "require_port",
    "require_text",
    "require_user_id",
)


def require_user_id(user_id: int) -> int:
    return require_strict_user_id(user_id)


def require_text(value: JSONValue | str | None, label: str) -> str:
    return require_trimmed_json_text(value, error_message=f"{label} is required.")


def require_port(value: JSONValue | int | None, label: str) -> int:
    if not is_strict_int(value) or value <= 0:
        raise ValidationError(f"{label} must be a positive integer.")
    return int(value)


def require_epoch_ms(value: JSONValue | int | None, label: str) -> int:
    return require_unix_epoch_ms(
        value,
        error_message=f"{label} must be a positive integer.",
        enforce_maximum=False,
    )


def optional_epoch_ms(value: JSONValue | int | None, *, label: str = "timestamp") -> int | None:
    if value is None:
        return None
    return require_epoch_ms(value, label)


def require_nonnegative_int(value: JSONValue | int | None, label: str) -> int:
    return require_row_non_negative_int(
        value,
        label=label,
        build_error=ValidationError,
        invalid_message=f"{label} must be a non-negative integer.",
        allow_numberish=False,
    )


def require_bool_int(value: JSONValue, label: str) -> int:
    return require_row_bool_int(
        value,
        label=label,
        build_error=ValidationError,
        invalid_message=f"{label} must be a boolean.",
        allow_numberish=False,
    )


def optional_json_list(value: JSONValue) -> str | None:
    return serialize_optional_json_list_field(
        value,
        error_message="value must be a list or null.",
    )


def optional_json_object(value: JSONValue) -> str | None:
    return serialize_optional_json_object_field(
        value,
        error_message="value must be an object or null.",
    )
