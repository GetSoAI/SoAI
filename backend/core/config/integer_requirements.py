"""SoAI - Strict integer configuration requirements [backend/core/config/integer_requirements.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.numeric import require_strict_int_at_least
from core.errors.exceptions import ConfigurationError, ValidationError
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import require_int_in_range_strict

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

__all__ = (
    "require_config_int_at_least",
    "require_config_int_between",
)


def _format_integer_bound(value: int) -> str:
    return f"{value:_}" if abs(value) >= 1_000_000 else str(value)


def require_config_int_at_least(value: ConfigValue, *, key: str, minimum: int) -> int:
    try:
        return require_strict_int_at_least(value, key=key, minimum=minimum)
    except ValidationError as exception:
        raise ConfigurationError(
            f"{key} must be >= {_format_integer_bound(minimum)}.",
        ) from exception


def require_config_int_between(
    value: ConfigValue,
    *,
    key: str,
    minimum: int,
    maximum: int,
) -> int:
    minimum_label = _format_integer_bound(minimum)
    maximum_label = _format_integer_bound(maximum)
    error_message = f"{key} must be between {minimum_label} and {maximum_label}."
    try:
        if not is_strict_int(value):
            raise ValidationError(error_message)
        return require_int_in_range_strict(
            value,
            minimum=minimum,
            maximum=maximum,
            error_message=error_message,
        )
    except ValidationError as exception:
        raise ConfigurationError(error_message) from exception
