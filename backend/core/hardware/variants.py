"""SoAI - Variant sizing and download estimation helpers [backend/core/hardware/variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "coerce_variant_size_bytes",
    "estimate_download_seconds",
)


def coerce_variant_size_bytes(variant: JSONDict) -> int | None:
    if not isinstance(variant, dict):
        return None
    size_value = variant.get("size_bytes")
    if isinstance(size_value, int | float) and math.isfinite(size_value) and (size_value > 0):
        try:
            return int(size_value)
        except (TypeError, ValueError, OverflowError):
            return None
    size_value = variant.get("size_gb")
    if isinstance(size_value, int | float) and math.isfinite(size_value) and (size_value > 0):
        try:
            return int(size_value * 1024**3)
        except (TypeError, ValueError, OverflowError):
            return None
    return None


def estimate_download_seconds(size_bytes: int | None, throughput_bps: float | None) -> float | None:
    if size_bytes is None or throughput_bps is None:
        return None
    if size_bytes <= 0 or throughput_bps <= 0:
        return None
    try:
        value = float(size_bytes) / float(throughput_bps)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value
