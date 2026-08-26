"""SoAI - NVIDIA settings GPU tuning operation handlers [backend/hardware/vendors/nvidia/tuning_nvidia_settings_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_settings_contract import (
    GPU_SETTING_CORE_CLOCK_FIELD,
    GPU_SETTING_FAN_SPEED_FIELD,
    GPU_SETTING_MEM_CLOCK_FIELD,
)
from core.validation.coercion import coerce_int_from_scalar
from hardware.gpu_tuning.service_parsing import (
    coerce_gpu_setting_int_for_apply,
    read_capability_setting_int,
)
from hardware.result_messages import append_log_message
from hardware.vendors.nvidia.tuning_error_reporting import (
    report_nvidia_tuning_exception,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict, JSONValue
    from hardware.vendors.nvidia.smi import NvidiaSettingsController

__all__ = (
    "apply_nvidia_settings_clock_offsets",
    "apply_nvidia_settings_fan_speed",
    "apply_nvidia_settings_reset_clocks",
)


def apply_nvidia_settings_fan_speed(
    *,
    logger: TraceLogger | None,
    vendor_id: int,
    fan_speed: JSONValue,
    errors: list[str],
    messages: list[str],
    controller: NvidiaSettingsController,
    operation: str,
) -> bool:
    try:
        if isinstance(fan_speed, str) and fan_speed.lower() == "auto":
            success, output = controller.reset_fan_control(vendor_id)
            message = "Fan control set to AUTO (nvidia-settings)."
        else:
            speed_value = coerce_gpu_setting_int_for_apply(
                fan_speed,
                GPU_SETTING_FAN_SPEED_FIELD,
                errors,
            )
            if speed_value is None:
                return False
            if speed_value < 0:
                errors.append("fan_speed must be a non-negative number.")
                return False
            success, output = controller.set_fan_speed(speed_value, vendor_id)
            message = f"Fan speed set to {speed_value}% (nvidia-settings)."
        if success:
            append_log_message(messages, logger, vendor_id, message)
        else:
            errors.append(f"nvidia-settings fan control failed: {output}")
        return True
    except RECOVERABLE_EXCEPTIONS as exception:
        if logger is not None:
            log_handled_exception(
                logger,
                exception,
                message=f"nvidia-settings fan control error: {exception}",
                operation=operation,
                details={"vendor_id": vendor_id},
                level="warning",
            )
        report_nvidia_tuning_exception(
            vendor_id=vendor_id,
            errors=errors,
            exception=exception,
            message=f"nvidia-settings fan control error: {exception}",
            operation=operation,
        )
        return True


def apply_nvidia_settings_reset_clocks(
    *,
    logger: TraceLogger | None,
    vendor_id: int,
    errors: list[str],
    messages: list[str],
    controller: NvidiaSettingsController,
    operation: str,
) -> None:
    try:
        success, output = controller.reset_clocks(vendor_id)
        if success:
            message = "Clock offsets reset to 0 (nvidia-settings)."
            append_log_message(messages, logger, vendor_id, message)
        else:
            errors.append(f"nvidia-settings clock reset failed: {output}")
    except RECOVERABLE_EXCEPTIONS as exception:
        if logger is not None:
            log_handled_exception(
                logger,
                exception,
                message=f"nvidia-settings clock reset error: {exception}",
                operation=operation,
                details={"vendor_id": vendor_id},
                level="warning",
            )
        report_nvidia_tuning_exception(
            vendor_id=vendor_id,
            errors=errors,
            exception=exception,
            message=f"nvidia-settings clock reset error: {exception}",
            operation=operation,
        )


def apply_nvidia_settings_clock_offsets(
    *,
    logger: TraceLogger | None,
    vendor_id: int,
    controller: NvidiaSettingsController,
    core_clock: JSONValue | None,
    mem_clock: JSONValue | None,
    caps: JSONDict,
    errors: list[str],
    messages: list[str],
    operation: str,
) -> bool:
    try:
        core_perf_level = _read_capability_perf_level(caps, "core_clock_mhz")
        mem_perf_level = _read_capability_perf_level(caps, "mem_clock_mhz")
        core_default: int | None = None
        mem_default: int | None = None
        if core_clock is not None and not (
            isinstance(core_clock, str) and core_clock.lower() == "auto"
        ):
            core_default = read_capability_setting_int(caps, "core_clock_mhz")
            if core_default is None:
                errors.append("Default core clock is unavailable.")
                return False
        if mem_clock is not None and not (
            isinstance(mem_clock, str) and mem_clock.lower() == "auto"
        ):
            mem_default = read_capability_setting_int(caps, "mem_clock_mhz")
            if mem_default is None:
                errors.append("Default memory clock is unavailable.")
                return False
        applied_parts: list[str] = []
        if core_clock is not None:
            if isinstance(core_clock, str) and core_clock.lower() == "auto":
                core_offset = 0
            else:
                core_value = coerce_gpu_setting_int_for_apply(
                    core_clock,
                    GPU_SETTING_CORE_CLOCK_FIELD,
                    errors,
                )
                if core_value is None:
                    return False
                if core_default is None:
                    errors.append("Default core clock is unavailable.")
                    return False
                core_offset = core_value - core_default
            core_success, core_output = controller.set_clock_offset(
                core_offset,
                vendor_id,
                core_perf_level,
            )
            if core_success:
                applied_parts.append(f"Core: {core_offset:+d}MHz")
            else:
                errors.append(f"Core clock setting failed: {core_output}")
                return True
        if mem_clock is not None:
            if isinstance(mem_clock, str) and mem_clock.lower() == "auto":
                mem_offset = 0
            else:
                mem_value = coerce_gpu_setting_int_for_apply(
                    mem_clock,
                    GPU_SETTING_MEM_CLOCK_FIELD,
                    errors,
                )
                if mem_value is None:
                    return False
                if mem_default is None:
                    errors.append("Default memory clock is unavailable.")
                    return False
                mem_offset = mem_value - mem_default
            mem_success, mem_output = controller.set_memory_offset(
                mem_offset,
                vendor_id,
                mem_perf_level,
            )
            if mem_success:
                applied_parts.append(f"Memory: {mem_offset:+d}MHz")
            else:
                errors.append(f"Memory clock setting failed: {mem_output}")
        if applied_parts:
            append_log_message(
                messages,
                logger,
                vendor_id,
                f"Clock offsets set to {', '.join(applied_parts)} (nvidia-settings).",
            )
        return True
    except RECOVERABLE_EXCEPTIONS as exception:
        if logger is not None:
            log_handled_exception(
                logger,
                exception,
                message=f"nvidia-settings clock setting error: {exception}",
                operation=operation,
                details={"vendor_id": vendor_id},
                level="warning",
            )
        report_nvidia_tuning_exception(
            vendor_id=vendor_id,
            errors=errors,
            exception=exception,
            message=f"nvidia-settings clock setting error: {exception}",
            operation=operation,
        )
        return True


def _read_capability_perf_level(caps: JSONDict, key: str) -> int | None:
    value = caps.get(key)
    if not isinstance(value, dict):
        return None
    return coerce_int_from_scalar(value.get("perf_level"))
