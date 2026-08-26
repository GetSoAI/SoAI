"""SoAI - Boolean parsing utilities [backend/core/validation/booleans.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, overload

from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue
    from core.types.json import JSONValue

    type BoolCoercible = JSONValue | ConfigValue

__all__ = (
    "parse_bool",
    "parse_bool_flag_or_none",
    "parse_bool_flag_with_default",
    "parse_bool_token_or_none",
    "parse_true_false_token_or_none",
)


@overload
def parse_bool(value: BoolCoercible, default: bool) -> bool: ...


@overload
def parse_bool(value: BoolCoercible, default: bool | None) -> bool | None: ...


@overload
def parse_bool(value: BoolCoercible) -> bool: ...


def parse_bool(value: BoolCoercible, default: bool | None = False) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        parsed_token = parse_bool_token_or_none(value)
        if parsed_token is not None:
            return parsed_token
        lowered = value.strip().lower()
        if lowered:
            try:
                numeric_value = float(lowered)
                return numeric_value != 0
            except ValueError as error:
                raise ValidationError(
                    "Invalid boolean string value.",
                    details={"value": value},
                ) from error
        return default
    raise ValidationError("Invalid boolean value type.", details={"type": type(value).__name__})


def parse_bool_token_or_none(value: BoolCoercible) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if is_strict_int(value):
        if value == 0:
            return False
        if value == 1:
            return True
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return None


def parse_bool_flag_or_none(value: BoolCoercible) -> bool | None:
    parsed = parse_bool_token_or_none(value)
    if parsed is not None:
        return parsed
    if is_strict_int(value):
        return bool(value)
    return None


def parse_bool_flag_with_default(value: BoolCoercible, *, default: bool) -> bool:
    parsed = parse_bool_flag_or_none(value)
    return default if parsed is None else bool(parsed)


def parse_true_false_token_or_none(value: BoolCoercible) -> bool | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None
