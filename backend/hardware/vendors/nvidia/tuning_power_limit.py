"""SoAI - NVIDIA NVML power-limit application [backend/hardware/vendors/nvidia/tuning_power_limit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable

from core.errors.exceptions import StateError
from core.logging.trace import TraceLogger
from core.types.json import JSONValue
from hardware.gpu_tuning.service_parsing import coerce_auto_or_gpu_setting_int

__all__ = ("apply_nvml_power_limit_setting",)


def apply_nvml_power_limit_setting(
    logger: TraceLogger | None,
    *,
    vendor_id: int,
    messages: list[str],
    handle: ctypes.c_void_p,
    power_limit: JSONValue,
    power_default_limit_function: Callable[[ctypes.c_void_p], int] | None,
    power_set_limit_function: Callable[[ctypes.c_void_p, int], None] | None,
) -> None:
    if not callable(power_default_limit_function) or not callable(power_set_limit_function):
        raise StateError("Power limit control unavailable.")
    is_auto, limit_value = coerce_auto_or_gpu_setting_int(power_limit)
    if is_auto:
        limit = power_default_limit_function(handle)
    else:
        if limit_value is None:
            raise StateError("Power limit must be numeric.")
        limit = limit_value * 1000
    power_set_limit_function(handle, limit)
    message = (
        f"Power limit reset to default ({limit // 1000}W)."
        if is_auto
        else f"Power limit set to {limit // 1000}W."
    )
    messages.append(message)
    if logger:
        logger.info("NVIDIA GPU %s %s", vendor_id, message)
