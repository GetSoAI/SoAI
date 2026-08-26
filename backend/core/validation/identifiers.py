"""SoAI - Identifier normalization and prefixed ID validation [backend/core/validation/identifiers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "collapse_identifier",
    "is_identifier_strictly_alnum",
    "optional_prefixed_identifier",
    "require_prefixed_identifier",
    "validate_safe_identifier",
)


def collapse_identifier(value: JSONValue) -> str:
    if not isinstance(value, str):
        raise ValidationError("Identifier value must be a string.")
    return value.lower().replace("-", "").replace("_", "")


def is_identifier_strictly_alnum(value: str | None) -> bool:
    if value is None:
        return False
    collapsed = collapse_identifier(value)
    return bool(collapsed) and collapsed.isalnum()


def require_prefixed_identifier(value: str, *, prefix: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or not normalized.startswith(prefix):
        raise ValidationError(f"{label} is invalid.")
    return normalized


def optional_prefixed_identifier(
    value: JSONValue | str | None,
    *,
    prefix: str,
    label: str,
) -> str | None:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        return None
    return require_prefixed_identifier(normalized, prefix=prefix, label=label)


def validate_safe_identifier(
    value: str | None,
    field_name: str,
    max_len: int,
    pattern: str,
) -> str | None:
    if value is None:
        return value
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{field_name} cannot be empty or contain only whitespace.")
    if not re.fullmatch(pattern, normalized) or ".." in normalized or len(normalized) > max_len:
        raise ValidationError(f"{field_name} is invalid (length, characters, or '..').")
    return normalized
