"""SoAI - AMD GPU tuning via AMD SMI [backend/hardware/vendors/amd/settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_operation_results import build_gpu_result
from core.logging.trace import get_logger
from core.types.json import is_json_value
from core.validation.coercion import coerce_int_from_scalar
from hardware.gpu_capabilities.payloads import read_control_capability_section
from hardware.gpu_tuning.service_parsing import is_auto_gpu_setting
from hardware.gpu_tuning.settings_request import GpuSettingsApplyRequest
from hardware.result_messages import (
    append_amd_log_message,
    build_gpu_result_message_lists,
)
from hardware.vendors.amd.amd_smi_parsing import select_amd_smi_level
from hardware.vendors.amd.availability import is_amd_smi_available
from hardware.vendors.amd.capabilities import sync_get_amd_capabilities
from hardware.vendors.amd.commands import (
    execute_amd_smi_command,
    execute_amd_smi_reset_command,
)
from hardware.vendors.amd.overdrive_apply import apply_amdgpu_overdrive_settings
from hardware.vendors.amd.overdrive_state import AMDGPU_OVERDRIVE_BACKEND

if TYPE_CHECKING:
    from core.logging.trace import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("sync_set_amd_settings",)

LOGGER_NAME = "SoAI.hardware.vendors.settings"
OPERATION_AMD_SETTINGS_SET_FAN_SPEED = "hardware.vendors.amd.settings.set_fan_speed"
OPERATION_AMD_SETTINGS_SET_POWER_LIMIT = "hardware.vendors.amd.settings.set_power_limit"
OPERATION_AMD_SETTINGS_RESET_CLOCKS = "hardware.vendors.amd.settings.reset_clocks"
OPERATION_AMD_SETTINGS_SET_CLOCKS = "hardware.vendors.amd.settings.set_clocks"
OPERATION_AMD_SETTINGS_SET_OVERDRIVE = "hardware.vendors.amd.settings.set_overdrive"


def sync_set_amd_settings(
    executor: CommandExecutorProtocol,
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    request: GpuSettingsApplyRequest,
    capabilities: JSONDict | None = None,
) -> JSONDict:
    def _coerce_levels(
        value: JSONValue,
    ) -> list[Mapping[str, JSONValue]] | None:
        if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
            return None
        levels: list[Mapping[str, JSONValue]] = []
        for item in value:
            if isinstance(item, Mapping):
                level: dict[str, JSONValue] = {}
                for key, val in item.items():
                    if not isinstance(key, str) or not is_json_value(val):
                        continue
                    level[key] = val
                if level:
                    levels.append(level)
        return levels or None

    control_backend = request.control_backend
    if control_backend is None:
        return build_gpu_result(errors=["AMD control backend is required."])
    if control_backend == AMDGPU_OVERDRIVE_BACKEND:
        return _set_amd_overdrive_settings(
            executor,
            logger,
            vendor_id,
            request=request,
            capabilities=capabilities,
        )
    if control_backend != "amd_smi":
        return build_gpu_result(errors=[f"AMD control backend '{control_backend}' is unsupported."])
    if not is_amd_smi_available():
        return build_gpu_result(errors=["amd-smi not found for AMD GPU control."])
    gpu_result, messages, errors = build_gpu_result_message_lists()
    power_limit = request.power_limit
    if power_limit is not None:
        try:
            if is_auto_gpu_setting(power_limit):
                execute_amd_smi_reset_command(executor, vendor_id, ["--power-cap"])
                message = "Power limit reset to default."
            else:
                value = coerce_int_from_scalar(power_limit)
                if value is None:
                    raise ValidationError("Invalid power limit value.")
                execute_amd_smi_command(executor, vendor_id, ["--power-cap", str(value)])
                message = f"Power limit set to {value}W."
            gpu_result["changed"] = True
            append_amd_log_message(messages, logger, vendor_id, message)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger or get_logger(LOGGER_NAME),
                exception,
                message="Failed to set AMD power limit.",
                operation=OPERATION_AMD_SETTINGS_SET_POWER_LIMIT,
                details={"vendor_id": vendor_id},
                level="warning",
            )
            errors.append(f"Failed to set power limit: {exception}")
            return gpu_result
    fan_speed = request.fan_speed
    if fan_speed is not None:
        try:
            if str(fan_speed).lower() == "auto":
                execute_amd_smi_command(executor, vendor_id, ["--perf-level", "AUTO"])
                message = "Fan speed reset to default."
            else:
                value = coerce_int_from_scalar(fan_speed)
                if value is None:
                    raise ValidationError("Invalid fan speed value.")
                execute_amd_smi_command(executor, vendor_id, ["--fan", str(value)])
                message = f"Fan speed set to {value}%."
            gpu_result["changed"] = True
            append_amd_log_message(messages, logger, vendor_id, message)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger or get_logger(LOGGER_NAME),
                exception,
                message="Failed to set AMD fan speed.",
                operation=OPERATION_AMD_SETTINGS_SET_FAN_SPEED,
                details={"vendor_id": vendor_id},
                level="warning",
            )
            errors.append(f"Failed to set fan speed: {exception}")
            return gpu_result
    if request.reset_clocks:
        try:
            execute_amd_smi_reset_command(executor, vendor_id, ["--clocks"])
            gpu_result["changed"] = True
            message = "Clock states reset to defaults."
            append_amd_log_message(messages, logger, vendor_id, message)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger or get_logger(LOGGER_NAME),
                exception,
                message="Failed to reset AMD clocks.",
                operation=OPERATION_AMD_SETTINGS_RESET_CLOCKS,
                details={"vendor_id": vendor_id},
                level="warning",
            )
            errors.append(f"Failed to reset clocks: {exception}")
            return gpu_result
    elif request.core_clock is not None or request.mem_clock is not None:
        cap_entry = (
            capabilities
            if isinstance(capabilities, dict)
            else sync_get_amd_capabilities(executor, logger, vendor_id)
        )
        core_caps = read_control_capability_section(cap_entry, "core_clock_mhz")
        mem_caps = read_control_capability_section(cap_entry, "mem_clock_mhz")

        def _resolve_auto_target(caps_entry: JSONDict) -> int | None:
            for key in ("default", "max", "current"):
                if (value := coerce_int_from_scalar(caps_entry.get(key))) is not None:
                    return value
            return None

        applied_parts: list[str] = []
        try:
            if request.core_clock is not None:
                core_levels = _coerce_levels(core_caps.get("levels"))
                if not core_levels:
                    raise ValidationError("Core clock adjustment is unavailable for this AMD GPU.")
                raw_core = request.core_clock
                if isinstance(raw_core, str) and raw_core.lower() == "auto":
                    core_target = _resolve_auto_target(core_caps)
                else:
                    core_target = coerce_int_from_scalar(raw_core)
                if core_target is None:
                    raise ValidationError("Invalid core clock value.")
                core_level, actual_core = select_amd_smi_level(core_levels, core_target)
                execute_amd_smi_command(
                    executor,
                    vendor_id,
                    ["--clk-level", "sclk", str(core_level)],
                )
                gpu_result["changed"] = True
                applied_parts.append(f"Core {actual_core}MHz (level {core_level})")
            if request.mem_clock is not None:
                mem_levels = _coerce_levels(mem_caps.get("levels"))
                if not mem_levels:
                    raise ValidationError(
                        "Memory clock adjustment is unavailable for this AMD GPU.",
                    )
                raw_mem = request.mem_clock
                if isinstance(raw_mem, str) and raw_mem.lower() == "auto":
                    mem_target = _resolve_auto_target(mem_caps)
                else:
                    mem_target = coerce_int_from_scalar(raw_mem)
                if mem_target is None:
                    raise ValidationError("Invalid memory clock value.")
                mem_level, actual_mem = select_amd_smi_level(mem_levels, mem_target)
                execute_amd_smi_command(
                    executor,
                    vendor_id,
                    ["--clk-level", "mclk", str(mem_level)],
                )
                gpu_result["changed"] = True
                applied_parts.append(f"Memory {actual_mem}MHz (level {mem_level})")
            if applied_parts:
                message = f"Clocks set to {', '.join(applied_parts)}."
                append_amd_log_message(messages, logger, vendor_id, message)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger or get_logger(LOGGER_NAME),
                exception,
                message="Failed to set AMD clocks.",
                operation=OPERATION_AMD_SETTINGS_SET_CLOCKS,
                details={"vendor_id": vendor_id},
                level="warning",
            )
            errors.append(f"Failed to set clocks: {exception}")
            return gpu_result
    return gpu_result


def _set_amd_overdrive_settings(
    executor: CommandExecutorProtocol,
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    request: GpuSettingsApplyRequest,
    capabilities: JSONDict | None,
) -> JSONDict:
    gpu_result, messages, errors = build_gpu_result_message_lists()
    caps = capabilities if isinstance(capabilities, dict) else {}
    pci_bdf_value = caps.get("overdrive_pci_bdf") or caps.get("pci_bdf")
    pci_bdf = pci_bdf_value if isinstance(pci_bdf_value, str) else None
    try:
        applied_parts = apply_amdgpu_overdrive_settings(
            executor,
            pci_bdf=pci_bdf,
            reset_clocks=request.reset_clocks,
            core_clock=request.core_clock,
            mem_clock=request.mem_clock,
        )
        if applied_parts:
            gpu_result["changed"] = True
            append_amd_log_message(
                messages,
                logger,
                vendor_id,
                f"OverDrive applied: {', '.join(applied_parts)}.",
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger or get_logger(LOGGER_NAME),
            exception,
            message="Failed to set AMD OverDrive controls.",
            operation=OPERATION_AMD_SETTINGS_SET_OVERDRIVE,
            details={"vendor_id": vendor_id},
            level="warning",
        )
        errors.append(f"Failed to set OverDrive controls: {exception}")
    return gpu_result
