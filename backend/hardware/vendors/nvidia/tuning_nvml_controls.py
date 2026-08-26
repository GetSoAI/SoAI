"""SoAI - NVML fan and clock tuning routines [backend/hardware/vendors/nvidia/tuning_nvml_controls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.imports.availability import module_available
from hardware.gpu_tuning.service_parsing import coerce_auto_or_gpu_setting_int
from hardware.result_messages import append_log_message

if TYPE_CHECKING:
    import ctypes

    from core.logging.protocols import TraceLogger
    from core.types.json import JSONValue

    type NvmlDeviceHandle = ctypes.c_void_p

__all__ = ("apply_nvml_fan_setting",)

pynvml_module_ref = None
if module_available("pynvml"):
    import pynvml

    pynvml_module_ref = pynvml


def apply_nvml_fan_setting(
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    messages: list[str],
    errors: list[str],
    handle: NvmlDeviceHandle,
    fan_speed: JSONValue,
) -> bool:
    pynvml_module = pynvml_module_ref
    if pynvml_module is None:
        errors.append("Failed to set fan speed: pynvml is unavailable.")
        return False
    try:
        try:
            device_set_default_fan_speed: Callable[..., None] | None = (
                pynvml_module.nvmlDeviceSetDefaultFanSpeed_v2
            )
        except AttributeError:
            device_set_default_fan_speed = None
        try:
            device_set_fan_speed: Callable[..., None] | None = (
                pynvml_module.nvmlDeviceSetFanSpeed_v2
            )
        except AttributeError:
            device_set_fan_speed = None
        if not callable(device_set_default_fan_speed) or not callable(device_set_fan_speed):
            raise StateError("Fan control unavailable.")
        is_auto, speed_value = coerce_auto_or_gpu_setting_int(fan_speed)
        if is_auto:
            _set_default_fan_speed(device_set_default_fan_speed, handle)
            message = "Fan control set to AUTO."
        else:
            if speed_value is None:
                raise StateError("Fan speed must be numeric.")
            device_set_fan_speed(handle, 0, speed_value)
            message = f"Manual fan speed set to {speed_value}%."
        append_log_message(messages, logger, vendor_id, message)
        return True
    except pynvml_module.NVMLError as exception:
        errors.append(f"Failed to set fan speed: {exception}")
    except (ValueError, RuntimeError) as exception:
        errors.append(f"Failed to set fan speed: {exception}")
    return False


def _set_default_fan_speed(
    setter: Callable[..., None],
    handle: NvmlDeviceHandle,
) -> None:
    try:
        setter(handle, 0)
    except TypeError as first_exception:
        try:
            setter(handle)
        except TypeError as second_exception:
            raise first_exception from second_exception
