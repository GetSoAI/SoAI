"""SoAI - NVML clock-offset range sanitization [backend/hardware/vendors/nvidia/nvml_clock_offset_sanitize.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.validation.strict_integer import is_strict_int

__all__ = ("MAX_PLAUSIBLE_OFFSET_MHZ", "resolve_offset_bounds")

MAX_PLAUSIBLE_OFFSET_MHZ = 100000


def _is_plausible_offset(value: int) -> bool:
    return -MAX_PLAUSIBLE_OFFSET_MHZ <= value <= MAX_PLAUSIBLE_OFFSET_MHZ


def resolve_offset_bounds(raw_min: int, raw_max: int) -> tuple[int, int] | None:
    if not is_strict_int(raw_min) or not is_strict_int(raw_max):
        return None
    if not _is_plausible_offset(raw_min) or not _is_plausible_offset(raw_max):
        return None
    if raw_min >= raw_max:
        return None
    return (raw_min, raw_max)
