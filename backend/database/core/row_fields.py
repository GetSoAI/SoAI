"""SoAI - Strict database row field validation [backend/database/core/row_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import (
    coerce_exact_int_or_none,
    is_strict_int,
    require_non_negative_exact_int,
    require_positive_exact_int,
)
from core.validation.record_fields import require_int, require_non_empty_str
from database.core.json_codec import (
    safe_json_deserialize_required_list,
    safe_json_deserialize_required_object,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteValue

    type ErrorBuilder = Callable[[str], Exception]

__all__ = (
    "coerce_row_optional_non_negative_int",
    "require_row_bool",
    "require_row_bool_int",
    "require_row_epoch_ms",
    "require_row_json_list",
    "require_row_json_object",
    "require_row_non_empty_str",
    "require_row_non_negative_int",
    "require_row_optional_json_list",
    "require_row_optional_json_object",
    "require_row_optional_non_negative_int",
    "require_row_positive_int",
)


def _build_error_message(label: str) -> str:
    if label.endswith("."):
        return label
    return f"{label} is missing or invalid."


def require_row_non_empty_str(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
) -> str:
    return require_non_empty_str(
        value,
        label=label,
        build_error=build_error,
        invalid_message=_build_error_message(label),
    )


def require_row_positive_int(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    minimum: int = 1,
) -> int:
    error_message = _build_error_message(label)
    try:
        normalized = require_positive_exact_int(
            value,
            type_message=error_message,
            range_message=error_message,
        )
    except ValidationError as exception:
        raise build_error(error_message) from exception
    if normalized < minimum:
        raise build_error(error_message)
    return int(normalized)


def require_row_non_negative_int(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
    allow_numberish: bool = True,
) -> int:
    error_message = invalid_message or _build_error_message(label)
    if not allow_numberish:
        return require_int(
            value,
            label=label,
            build_error=build_error,
            minimum=0,
            invalid_message=error_message,
        )
    try:
        return require_non_negative_exact_int(
            value,
            type_message=error_message,
            range_message=error_message,
        )
    except ValidationError as exception:
        raise build_error(error_message) from exception


def require_row_optional_non_negative_int(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
) -> int | None:
    if value is None:
        return None
    error_message = _build_error_message(label)
    normalized = coerce_exact_int_or_none(value)
    if normalized is None or normalized < 0:
        raise build_error(error_message)
    return int(normalized)


def coerce_row_optional_non_negative_int(value: JSONValue) -> int | None:
    if value is None:
        return None
    normalized = coerce_exact_int_or_none(value)
    if normalized is None or normalized < 0:
        return None
    return int(normalized)


def require_row_epoch_ms(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
) -> int:
    try:
        return require_unix_epoch_ms(
            value,
            error_message=_build_error_message(label),
            enforce_maximum=False,
        )
    except ValidationError as exception:
        raise build_error(_build_error_message(label)) from exception


def require_row_bool(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
) -> bool:
    if isinstance(value, bool):
        return value
    normalized = coerce_exact_int_or_none(value)
    if normalized not in (0, 1):
        raise build_error(_build_error_message(label))
    return normalized == 1


def require_row_bool_int(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
    allow_numberish: bool = True,
) -> int:
    if value is True:
        return 1
    if value is False:
        return 0
    if allow_numberish:
        normalized = coerce_exact_int_or_none(value)
    elif is_strict_int(value):
        normalized = value
    else:
        normalized = None
    if normalized in (0, 1):
        return int(normalized)
    raise build_error(invalid_message or _build_error_message(label))


def require_row_json_object(
    value: SQLiteValue,
    *,
    label: str,
    build_error: ErrorBuilder,
) -> JSONDict:
    error_message = _build_error_message(label)
    try:
        return safe_json_deserialize_required_object(value, error_message=error_message)
    except ValidationError as exception:
        raise build_error(error_message) from exception


def require_row_optional_json_object(
    value: SQLiteValue,
    *,
    label: str,
    build_error: ErrorBuilder,
) -> JSONDict | None:
    if value is None:
        return None
    return require_row_json_object(value, label=label, build_error=build_error)


def require_row_json_list(
    value: SQLiteValue,
    *,
    label: str,
    build_error: ErrorBuilder,
) -> list[JSONValue]:
    error_message = _build_error_message(label)
    try:
        return safe_json_deserialize_required_list(value, error_message=error_message)
    except ValidationError as exception:
        raise build_error(error_message) from exception


def require_row_optional_json_list(
    value: SQLiteValue,
    *,
    label: str,
    build_error: ErrorBuilder,
) -> list[JSONValue] | None:
    if value is None:
        return None
    return require_row_json_list(value, label=label, build_error=build_error)
