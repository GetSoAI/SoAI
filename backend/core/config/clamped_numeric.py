"""SoAI - Min-clamped configuration numeric readers [backend/core/config/clamped_numeric.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import os
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.config.value_types import ConfigValue
    from core.types.json import JSONValue

__all__ = (
    "read_config_int_min_clamped",
    "read_config_nonnegative_int",
    "read_min_clamped_float",
    "read_min_clamped_int",
    "require_positive_numeric_config",
)


def read_config_int_min_clamped(
    config: ConfigProtocol,
    key: str,
    default: int,
    *,
    minimum: int,
) -> int:
    value = config.get(key, default)
    if value is None or (isinstance(value, str) and not value.strip()):
        return max(int(minimum), int(default))
    resolved = _coerce_config_int(value, key=key)
    return max(int(minimum), resolved)


def _coerce_config_int(value: ConfigValue, *, key: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{key} must be an integer.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValidationError(f"{key} must be finite.")
        if not value.is_integer():
            raise ValidationError(f"{key} must be an integer.")
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValidationError(f"{key} must be an integer.")
        try:
            return int(stripped)
        except ValueError as exception:
            raise ValidationError(f"{key} must be an integer.") from exception
    if isinstance(value, os.PathLike):
        return _coerce_config_int(os.fspath(value), key=key)
    raise ValidationError(f"{key} must be an integer.")


def read_config_nonnegative_int(
    config: ConfigProtocol | Mapping[str, JSONValue],
    key: str,
    default: int,
) -> int:
    raw_value = config.get(key, default)
    if isinstance(raw_value, bool):
        return max(default, 0)
    if not isinstance(raw_value, int | float | str):
        return max(default, 0)
    if isinstance(raw_value, float) and not math.isfinite(raw_value):
        return max(default, 0)
    try:
        value = int(raw_value)
    except (OverflowError, TypeError, ValueError):
        return max(default, 0)
    return max(value, 0)


def require_positive_numeric_config(
    value: ConfigValue,
    *,
    key: str,
    build_error: Callable[[str], Exception] = ValidationError,
) -> float:
    numeric_message = f"{key} must be numeric."
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise build_error(numeric_message)
    try:
        parsed = float(value)
    except ValueError as exception:
        raise build_error(numeric_message) from exception
    if not math.isfinite(parsed):
        raise build_error(f"{key} must be finite.")
    if parsed <= 0:
        raise build_error(f"{key} must be greater than 0.")
    return parsed


def read_min_clamped_float(
    config: ConfigProtocol,
    key: str,
    default: float,
    *,
    minimum: float,
) -> float:
    raw_value = config.get(key, default)
    if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
        return max(float(minimum), float(default))
    if isinstance(raw_value, bool):
        raise ValidationError(f"{key} must be a number.")
    try:
        parsed = _coerce_config_float(raw_value, key=key)
    except (TypeError, ValueError) as exception:
        raise ValidationError(f"{key} must be a number.") from exception
    if not math.isfinite(parsed):
        raise ValidationError(f"{key} must be finite.")
    return max(float(minimum), float(parsed))


def _coerce_config_float(value: ConfigValue, *, key: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{key} must be a number.")
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValidationError(f"{key} must be a number.")
        return float(stripped)
    if isinstance(value, os.PathLike):
        return _coerce_config_float(os.fspath(value), key=key)
    raise ValidationError(f"{key} must be a number.")


def read_min_clamped_int(
    config: ConfigProtocol,
    key: str,
    default: int,
    *,
    minimum: int,
) -> int:
    raw_value = config.get(key, default)
    if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
        return max(int(minimum), int(default))
    return max(int(minimum), _coerce_config_int(raw_value, key=key))
