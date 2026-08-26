"""SoAI - Byte size parsing and coercion for JSON/text inputs [backend/core/validation/byte_sizes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.validation.text_numbers import coerce_float_from_text

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("coerce_optional_size_bytes",)


def coerce_optional_size_bytes(value: JSONValue) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        if value < 0:
            return None
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value < 0:
            return None
        return int(value)
    if isinstance(value, str):
        number = coerce_float_from_text(value, default=None)
        if number is None:
            return None
        if number < 0:
            return None
        lower = value.lower()
        if "tb" in lower:
            multiplier = 1024**4
        elif "gb" in lower:
            multiplier = 1024**3
        elif "mb" in lower:
            multiplier = 1024**2
        elif "kb" in lower:
            multiplier = 1024
        else:
            multiplier = 1
        return int(number * multiplier)
    return None
