"""SoAI - Numberish integer requirement helpers [backend/core/validation/numberish.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.integers import coerce_exact_int_or_none

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "require_int_from_numberish",
    "require_optional_int_from_numberish",
)


def require_int_from_numberish(
    value: JSONValue,
    *,
    field: str,
    bool_message: str | None = None,
    invalid_message: str | None = None,
) -> int:
    resolved_bool_message = bool_message or f"{field} must be an int, not bool."
    resolved_invalid_message = invalid_message or f"{field} must be an int."
    if isinstance(value, bool):
        raise ValidationError(resolved_bool_message)
    parsed = coerce_exact_int_or_none(value)
    if parsed is None:
        raise ValidationError(resolved_invalid_message)
    return parsed


def require_optional_int_from_numberish(value: JSONValue, *, field: str) -> int | None:
    if value is None:
        return None
    return require_int_from_numberish(
        value,
        field=field,
        bool_message=f"{field} must be an int, not bool.",
        invalid_message=f"{field} must be an int.",
    )
