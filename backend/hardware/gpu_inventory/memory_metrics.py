"""SoAI - GPU memory metric coercion [backend/hardware/gpu_inventory/memory_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.validation.coercion import coerce_non_negative_int_from_numberish
from core.validation.text_numbers import coerce_float_from_text

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "bytes_to_mebibytes",
    "coerce_nonnegative_memory_bytes",
    "memory_percent_used",
)


def coerce_nonnegative_memory_bytes(value: JSONValue) -> int:
    if isinstance(value, bool):
        return 0
    float_value = coerce_float_from_text(value)
    if float_value is not None and not math.isfinite(float_value):
        return 0
    return coerce_non_negative_int_from_numberish(float_value if float_value is not None else value)


def bytes_to_mebibytes(value: int) -> int:
    if value <= 0:
        return 0
    return value // 1024**2


def memory_percent_used(used_value: int, total_value: int) -> float:
    if total_value <= 0 or used_value <= 0:
        return 0.0
    return round(min(100.0, used_value * 100 / total_value), 2)
