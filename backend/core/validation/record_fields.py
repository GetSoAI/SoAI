"""SoAI - Strict JSON record field validation helpers [backend/core/validation/record_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict, coerce_str_list
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.types.json import JSONDict, JSONValue

    type ErrorBuilder = Callable[[str], Exception]

__all__ = (
    "require_bool",
    "require_int",
    "require_json_list",
    "require_json_object",
    "require_json_object_list",
    "require_non_empty_str",
    "require_number",
    "require_optional_bool",
    "require_optional_int",
    "require_optional_json_list",
    "require_optional_json_object",
    "require_optional_non_empty_str",
    "require_optional_str",
    "require_scalar",
    "require_str_list",
)


def require_non_empty_str(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
) -> str:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        raise build_error(invalid_message or f"{label} is invalid.")
    return normalized


def require_optional_str(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
) -> str | None:
    if value is None:
        return None
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None and not isinstance(value, str):
        raise build_error(invalid_message or f"{label} is invalid.")
    return normalized


def require_optional_non_empty_str(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
) -> str | None:
    if value is None:
        return None
    return require_non_empty_str(
        value,
        label=label,
        build_error=build_error,
        invalid_message=invalid_message,
    )


def require_int(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    minimum: int | None = None,
    invalid_message: str | None = None,
) -> int:
    if not is_strict_int(value):
        raise build_error(invalid_message or f"{label} is invalid.")
    if minimum is not None and value < minimum:
        raise build_error(invalid_message or f"{label} is invalid.")
    return value


def require_optional_int(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    minimum: int | None = None,
    invalid_message: str | None = None,
) -> int | None:
    if value is None:
        return None
    if not is_strict_int(value):
        raise build_error(invalid_message or f"{label} is invalid.")
    if minimum is not None and value < minimum:
        raise build_error(invalid_message or f"{label} is invalid.")
    return value


def require_bool(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
) -> bool:
    if isinstance(value, bool):
        return value
    raise build_error(invalid_message or f"{label} is invalid.")


def require_optional_bool(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise build_error(invalid_message or f"{label} is invalid.")


def require_json_object(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
) -> JSONDict:
    normalized = coerce_json_dict(value)
    if normalized is None:
        raise build_error(invalid_message or f"{label} is invalid.")
    return normalized


def require_optional_json_object(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
) -> JSONDict | None:
    if value is None:
        return None
    return require_json_object(
        value,
        label=label,
        build_error=build_error,
        invalid_message=invalid_message,
    )


def require_json_list(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
) -> list[JSONValue]:
    if not isinstance(value, list):
        raise build_error(invalid_message or f"{label} is invalid.")
    return list(value)


def require_optional_json_list(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
) -> list[JSONValue] | None:
    if value is None:
        return None
    return require_json_list(
        value,
        label=label,
        build_error=build_error,
        invalid_message=invalid_message,
    )


def require_json_object_list(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
    entry_message: str | None = None,
) -> list[JSONDict]:
    items = require_json_list(
        value,
        label=label,
        build_error=build_error,
        invalid_message=invalid_message,
    )
    normalized: list[JSONDict] = []
    for item in items:
        item_object = coerce_json_dict(item)
        if item_object is None:
            raise build_error(entry_message or f"{label} contains an invalid object.")
        normalized.append(item_object)
    return normalized


def require_str_list(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    allow_empty: bool = False,
    strip_items: bool = True,
    reject_empty_items: bool = True,
    invalid_message: str | None = None,
    entry_message: str | None = None,
) -> list[str]:
    normalized = coerce_str_list(value, strip_items=strip_items)
    if normalized is None:
        raise build_error(invalid_message or f"{label} is invalid.")
    if reject_empty_items and any(not item for item in normalized):
        raise build_error(entry_message or invalid_message or f"{label} is invalid.")
    if not allow_empty and not normalized:
        raise build_error(invalid_message or f"{label} is invalid.")
    return normalized


def require_number(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
    finite_message: str | None = None,
) -> int | float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise build_error(invalid_message or f"{label} is invalid.")
    if isinstance(value, float) and not math.isfinite(value):
        raise build_error(finite_message or invalid_message or f"{label} is invalid.")
    return value


def require_scalar(
    value: JSONValue,
    *,
    label: str,
    build_error: ErrorBuilder,
    invalid_message: str | None = None,
    finite_message: str | None = None,
) -> str | int | float:
    if isinstance(value, str):
        return value
    return require_number(
        value,
        label=label,
        build_error=build_error,
        invalid_message=invalid_message,
        finite_message=finite_message,
    )
