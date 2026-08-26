"""SoAI - Task identifier and pagination normalization helpers [backend/core/tasks/identifiers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue
from core.validation.integers import is_strict_int

__all__ = (
    "normalize_optional_task_id",
    "require_non_negative_offset",
    "require_positive_limit",
    "require_task_id",
    "validate_optional_task_id",
)

_UUID_V4_REGEX = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_TASK_HEX_ID_REGEX = r"^task_[0-9a-f]{32}$"


def normalize_optional_task_id(value: JSONValue) -> str | None:
    if value is None or not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def require_task_id(value: JSONValue, *, error_message: str) -> str:
    normalized = normalize_optional_task_id(value)
    if normalized is None:
        raise ValidationError(error_message)
    return normalized


def validate_optional_task_id(task_id: JSONValue, field_name: str = "task_id") -> str | None:
    if task_id is None:
        return None
    if not isinstance(task_id, str):
        raise ValidationError(f"{field_name} must be a string.")
    normalized = task_id.strip().lower()
    if not normalized:
        raise ValidationError(f"{field_name} cannot be empty or whitespace.")
    if (re.fullmatch(_UUID_V4_REGEX, normalized, flags=re.IGNORECASE) is not None) or (
        re.fullmatch(_TASK_HEX_ID_REGEX, normalized, flags=re.IGNORECASE) is not None
    ):
        return normalized
    raise ValidationError(f"{field_name} must be a valid UUID v4 or a server-generated task id.")


def require_positive_limit(
    value: int,
    *,
    error_message: str,
    minimum: int = 1,
    maximum: int | None = None,
) -> int:
    if not is_strict_int(value) or value < int(minimum):
        raise ValidationError(error_message)
    if maximum is not None and value > int(maximum):
        raise ValidationError(error_message)
    return int(value)


def require_non_negative_offset(value: int, *, error_message: str) -> int:
    if not is_strict_int(value) or value < 0:
        raise ValidationError(error_message)
    return int(value)
