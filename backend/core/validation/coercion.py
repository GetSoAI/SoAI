"""SoAI - Type coercion utilities [backend/core/validation/coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue, is_json_value

if TYPE_CHECKING:
    type CoercibleValue = JSONValue | bytes | bytearray

__all__ = (
    "coerce_float",
    "coerce_float_from_scalar_text_bytes",
    "coerce_float_with_bool",
    "coerce_int",
    "coerce_int_from_numberish",
    "coerce_int_from_scalar",
    "coerce_int_strict",
    "coerce_json_dict_stringify_non_json_values",
    "coerce_json_value",
    "coerce_non_negative_int_from_numberish",
    "coerce_rollback_ms",
)


def coerce_rollback_ms(
    value: float | str | None,
    *,
    default_ms: int = 120_000,
    minimum_ms: int = 1,
    maximum_ms: int = 3_600_000,
) -> int:
    if value is None:
        return default_ms
    if isinstance(value, bool):
        raise ValidationError("rollback_ms must be an integer.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValidationError("rollback_ms must be an integer.")
    try:
        candidate = int(value)
    except (TypeError, ValueError) as exception:
        raise ValidationError("rollback_ms must be an integer.") from exception
    return max(minimum_ms, min(maximum_ms, candidate))


def coerce_int_from_numberish(value: CoercibleValue) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = Decimal(stripped)
        except InvalidOperation:
            return None
        if not parsed.is_finite():
            return None
        return int(parsed)
    return None


def coerce_non_negative_int_from_numberish(value: CoercibleValue) -> int:
    parsed = coerce_int_from_numberish(value)
    if parsed is None:
        return 0
    return max(0, parsed)


def coerce_int(value: CoercibleValue) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return int(value)
    if isinstance(value, str | bytes | bytearray):
        try:
            if isinstance(value, str):
                stripped = value.strip()
            else:
                stripped = value.decode("utf-8").strip()
            if not stripped:
                return None
            return int(stripped)
        except ValueError:
            return None
    return None


def coerce_int_from_scalar(value: CoercibleValue) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return int(value)
    if isinstance(value, str):
        try:
            stripped = value.strip()
            if not stripped:
                return None
            return int(stripped)
        except ValueError:
            return None
    return None


def coerce_int_strict(value: CoercibleValue) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return 0
        return int(value)
    if isinstance(value, str):
        try:
            stripped = value.strip()
            if not stripped:
                return 0
            return int(stripped)
        except ValueError:
            return 0
    return 0


def coerce_float(value: CoercibleValue) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        result = float(value)
        if not math.isfinite(result):
            return None
        return result
    if isinstance(value, str):
        try:
            stripped = value.strip()
            if not stripped:
                return None
            result = float(stripped)
            if not math.isfinite(result):
                return None
            return result
        except ValueError:
            return None
    return None


def coerce_float_from_scalar_text_bytes(value: CoercibleValue) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        result = float(value)
        if not math.isfinite(result):
            return None
        return result
    if isinstance(value, bytes | bytearray):
        text = bytes(value).decode("utf-8", errors="replace").strip()
    elif isinstance(value, str):
        text = value.strip()
    else:
        return None
    if not text:
        return None
    try:
        result = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def coerce_float_with_bool(value: CoercibleValue) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        result = float(value)
        if not math.isfinite(result):
            return None
        return result
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            result = float(stripped)
        except ValueError:
            return None
        if not math.isfinite(result):
            return None
        return result
    return None


def coerce_json_dict_stringify_non_json_values(value: CoercibleValue) -> JSONDict:
    if not isinstance(value, dict):
        return {}
    result: JSONDict = {}
    for key, item in value.items():
        if not isinstance(key, str):
            continue
        if is_json_value(item):
            result[key] = item
        else:
            result[key] = str(item)
    return result


def coerce_json_value(value: CoercibleValue) -> JSONValue | None:
    if is_json_value(value):
        return value
    return None
