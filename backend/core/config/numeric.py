"""SoAI - Configuration-focused numeric coercion helpers [backend/core/config/numeric.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import os
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from core.errors.exceptions import ConfigurationError, ValidationError
from core.logging.protocols import LoggerProtocol
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

    type NumericCoercible = ConfigValue

__all__ = (
    "coerce_float_or_none",
    "coerce_int_or_none",
    "coerce_positive_float",
    "coerce_positive_int",
    "coerce_positive_numeric",
    "is_strict_int",
    "require_strict_int_at_least",
    "resolve_default_numeric",
)


def _coerce_int_value(value: NumericCoercible) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValidationError("Float value must be finite.")
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValidationError("String value is empty.")
        try:
            parsed = Decimal(stripped)
        except InvalidOperation as exception:
            raise ValidationError("String value is not a valid number.") from exception
        return int(parsed)
    if isinstance(value, os.PathLike):
        return _coerce_int_value(os.fspath(value))
    raise TypeError(f"Unsupported numeric value type: {type(value).__name__}")


def _coerce_float_value(value: NumericCoercible) -> float:
    if isinstance(value, bool):
        raise ValidationError("Boolean value is not a valid number.")
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValidationError("String value is empty.")
        try:
            return float(stripped)
        except ValueError as exception:
            raise ValidationError("String value is not a valid number.") from exception
    if isinstance(value, os.PathLike):
        return _coerce_float_value(os.fspath(value))
    raise TypeError(f"Unsupported numeric value type: {type(value).__name__}")


def coerce_float_or_none(value: NumericCoercible) -> float | None:
    if value is None:
        return None
    try:
        return _coerce_float_value(value)
    except (TypeError, ValidationError):
        return None


def coerce_int_or_none(
    value: NumericCoercible,
    *,
    minimum: int,
    invalid_message: str,
    below_minimum_message: str | None = None,
    logger: LoggerProtocol | None = None,
) -> int | None:
    if value is None or isinstance(value, bool):
        _log_invalid_config_integer(logger, invalid_message)
        return None
    try:
        resolved = _coerce_strict_config_int_value(value)
    except (TypeError, ValidationError, ValueError):
        _log_invalid_config_integer(logger, invalid_message)
        return None
    if resolved < minimum:
        _log_invalid_config_integer(logger, below_minimum_message or invalid_message)
        return None
    return resolved


def require_strict_int_at_least(
    value: NumericCoercible,
    *,
    key: str,
    minimum: int,
) -> int:
    if not is_strict_int(value) or value < minimum:
        raise ValidationError(f"Invalid configuration: {key} must be an integer >= {minimum}")
    return value


def _log_invalid_config_integer(logger: LoggerProtocol | None, message: str) -> None:
    if logger is not None:
        logger.error(message)


def _coerce_strict_config_int_value(value: NumericCoercible) -> int:
    if isinstance(value, bool):
        raise ValidationError("Boolean value is not a valid integer.")
    if isinstance(value, int | float):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValidationError("Float value must be finite.")
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValidationError("String value is empty.")
        return int(stripped)
    if isinstance(value, os.PathLike):
        return _coerce_strict_config_int_value(os.fspath(value))
    raise TypeError(f"Unsupported integer value type: {type(value).__name__}")


def resolve_default_numeric[Numeric: int | float](
    default_value: NumericCoercible,
    *,
    minimum: Numeric,
    maximum: Numeric | None = None,
    label: str | None,
    description: str,
    converter: Callable[[NumericCoercible], Numeric],
) -> Numeric:
    try:
        resolved_default = converter(default_value)
    except (TypeError, ValidationError, ValueError) as exception:
        name = label or "value"
        raise ConfigurationError(f"Default {name} must be a valid {description}.") from exception
    if float(resolved_default) < float(minimum):
        name = label or "value"
        raise ConfigurationError(f"Default {name} must be >= {minimum}.")
    if maximum is not None and float(resolved_default) > float(maximum):
        name = label or "value"
        raise ConfigurationError(f"Default {name} must be <= {maximum}.")
    return resolved_default


def coerce_positive_int(
    value: NumericCoercible,
    *,
    default: int,
    minimum: int = 1,
    maximum: int | None = None,
    label: str | None = None,
    logger: LoggerProtocol | None = None,
) -> int:
    return coerce_positive_numeric(
        value,
        default=default,
        minimum=minimum,
        maximum=maximum,
        label=label,
        logger=logger,
        description="integer",
        converter=_coerce_int_value,
        invalid_message=_invalid_non_positive_message,
    )


def coerce_positive_float(
    value: NumericCoercible,
    *,
    default: float,
    minimum: float = 0.0,
    maximum: float | None = None,
    label: str | None = None,
    logger: LoggerProtocol | None = None,
) -> float:
    return coerce_positive_numeric(
        value,
        default=default,
        minimum=minimum,
        maximum=maximum,
        label=label,
        logger=logger,
        description="number",
        converter=_coerce_float_value,
        invalid_message=_invalid_value_message,
    )


def coerce_positive_numeric[Numeric: int | float](
    value: NumericCoercible,
    *,
    default: Numeric,
    minimum: Numeric,
    maximum: Numeric | None = None,
    label: str | None,
    logger: LoggerProtocol | None,
    description: str,
    converter: Callable[[NumericCoercible], Numeric],
    invalid_message: Callable[[NumericCoercible, str | None], str],
) -> Numeric:
    if value is None or (isinstance(value, str) and (not value.strip())):
        return resolve_default_numeric(
            default,
            minimum=minimum,
            maximum=maximum,
            label=label,
            description=description,
            converter=converter,
        )
    try:
        numeric = converter(value)
    except (TypeError, ValidationError, ValueError) as exception:
        message = invalid_message(value, label)
        if logger:
            logger.warning(message)
        raise ValidationError(message) from exception
    if float(numeric) < float(minimum):
        message = invalid_message(value, label)
        if logger:
            logger.warning(message)
        raise ValidationError(message)
    if maximum is not None and float(numeric) > float(maximum):
        name = label or "value"
        if logger:
            logger.warning(
                "Config %s value %s exceeds maximum %s; clamping.",
                name,
                numeric,
                maximum,
            )
        return maximum
    return numeric


def _invalid_non_positive_message(value: NumericCoercible, label: str | None) -> str:
    return (
        f"Invalid or non-positive {label} '{value}'."
        if label
        else f"Invalid or non-positive value '{value}'."
    )


def _invalid_value_message(value: NumericCoercible, label: str | None) -> str:
    return f"Invalid {label} '{value}'." if label else f"Invalid value '{value}'."
