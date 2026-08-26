"""SoAI - Strict runtime config requirements [backend/core/config/strict_requirements.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ConfigurationError, ValidationError
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_unit_interval_ratio_strict,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "require_config_non_negative_int",
    "require_config_unit_interval_ratio",
)


def require_config_unit_interval_ratio(
    config: ConfigProtocol,
    *,
    key: str,
    error_message: str,
) -> float:
    try:
        return require_unit_interval_ratio_strict(
            config.get_float(key),
            error_message=error_message,
        )
    except ValidationError as exception:
        raise ConfigurationError(error_message) from exception


def require_config_non_negative_int(
    config: ConfigProtocol,
    *,
    key: str,
    error_message: str,
) -> int:
    try:
        return require_non_negative_int_strict(
            config.get_int(key),
            error_message=error_message,
        )
    except ValidationError as exception:
        raise ConfigurationError(error_message) from exception
