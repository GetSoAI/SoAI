"""SoAI - Config byte-size coercion helpers [backend/core/config/byte_sizes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.errors.exceptions import ConfigurationError, ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.config.protocols import ConfigValue

__all__ = (
    "GIB_BYTES",
    "MIB_BYTES",
    "mib_to_bytes",
    "require_config_mib_to_bytes",
)

MIB_BYTES = 1024 * 1024
GIB_BYTES = 1024 * MIB_BYTES


def mib_to_bytes(mib: float) -> int:
    if isinstance(mib, bool):
        raise ValidationError("MiB value must be numeric, not boolean.")
    if isinstance(mib, int):
        return mib * MIB_BYTES
    numeric_mib = float(mib)
    if not math.isfinite(numeric_mib):
        raise ValidationError("MiB value must be finite.")
    byte_value = numeric_mib * MIB_BYTES
    if not math.isfinite(byte_value):
        raise ValidationError("MiB byte value must be finite.")
    return int(byte_value)


def require_config_mib_to_bytes(
    value: ConfigValue | None,
    *,
    field: str,
    missing_message: str | None = None,
    invalid_message: str | None = None,
    positive_message: str | None = None,
    allow_zero: bool = False,
    build_error: Callable[[str], Exception] = ConfigurationError,
) -> int:
    resolved_invalid_message = invalid_message or f"{field} must be a valid integer."
    if value is None:
        raise build_error(missing_message or f"{field} is missing.")
    if isinstance(value, bool):
        raise build_error(resolved_invalid_message)
    if isinstance(value, int | float):
        if isinstance(value, float) and not math.isfinite(value):
            raise build_error(resolved_invalid_message)
        parsed_mib = int(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise build_error(resolved_invalid_message)
        try:
            parsed_mib = int(stripped)
        except ValueError as exception:
            raise build_error(resolved_invalid_message) from exception
    else:
        raise build_error(resolved_invalid_message)
    if parsed_mib < 0 or (parsed_mib == 0 and not allow_zero):
        raise build_error(positive_message or f"{field} must be greater than zero.")
    return mib_to_bytes(parsed_mib)
