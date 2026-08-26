"""SoAI - JSON value coercion for history requests [backend/core/history/request/coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.history.request.models import NumericInput
    from core.types.json import JSONValue

__all__ = (
    "coerce_numeric_input",
    "coerce_numeric_sequence",
    "coerce_str_sequence",
)


def coerce_numeric_input(value: JSONValue, *, field: str) -> NumericInput:
    if isinstance(value, bool) or value is None:
        raise ValidationError(f"{field} must be a number or numeric string")
    if isinstance(value, int | float | str):
        return value
    raise ValidationError(f"{field} must be a number or numeric string")


def coerce_str_sequence(value: JSONValue, *, field: str) -> Sequence[str]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ValidationError(f"{field} must be a list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValidationError(f"{field} must contain only non-empty strings")
        result.append(item)
    if not result:
        raise ValidationError(f"{field} must contain at least one value")
    return result


def coerce_numeric_sequence(value: JSONValue, *, field: str) -> Sequence[NumericInput] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ValidationError(f"{field} must be a list of numbers")
    result: list[NumericInput] = []
    for item in value:
        if isinstance(item, bool) or item is None:
            raise ValidationError(f"{field} must contain only numeric values")
        if not isinstance(item, int | float | str):
            raise ValidationError(f"{field} must contain only numeric values")
        result.append(item)
    return result
