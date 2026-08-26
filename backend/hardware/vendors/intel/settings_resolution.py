"""SoAI - Intel GPU settings command resolution [backend/hardware/vendors/intel/settings_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.validation.coercion import coerce_int_from_numberish
from hardware.gpu_capabilities.payloads import read_control_capability_section
from hardware.gpu_tuning.service_parsing import is_auto_gpu_setting
from hardware.vendors.intel.capabilities import sync_get_intel_capabilities

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict
    from hardware.gpu_tuning.settings_request import GpuSettingsApplyRequest

__all__ = ("IntelApplyStep", "resolve_intel_apply_commands")

FAN_UNAVAILABLE_MESSAGE = "Intel fan speed adjustment is unavailable through this backend."
MEMORY_UNAVAILABLE_MESSAGE = "Intel memory clock adjustment is unavailable through this backend."


@dataclass(frozen=True, slots=True)
class IntelApplyStep:
    label: str
    args: tuple[str, ...] | None
    message: str


def resolve_intel_apply_commands(
    executor: CommandExecutorProtocol,
    logger: TraceLogger | None,
    vendor_id: int,
    request: GpuSettingsApplyRequest,
    capabilities: JSONDict | None,
) -> list[IntelApplyStep]:
    cap_payload = _resolve_capabilities(executor, logger, vendor_id, request, capabilities)
    steps: list[IntelApplyStep] = []
    power_step = _resolve_power_command(request, cap_payload)
    if power_step is not None:
        steps.append(power_step)
    if request.fan_speed is not None:
        steps.append(IntelApplyStep("fan speed", None, FAN_UNAVAILABLE_MESSAGE))
    clock_step = _resolve_clock_command(request, cap_payload)
    if clock_step is not None:
        steps.append(clock_step)
    if request.mem_clock is not None:
        steps.append(IntelApplyStep("memory clock", None, MEMORY_UNAVAILABLE_MESSAGE))
    return steps


def _resolve_capabilities(
    executor: CommandExecutorProtocol,
    logger: TraceLogger | None,
    vendor_id: int,
    request: GpuSettingsApplyRequest,
    capabilities: JSONDict | None,
) -> JSONDict:
    if request.power_limit is None and request.core_clock is None and not request.reset_clocks:
        return capabilities if isinstance(capabilities, dict) else {}
    return (
        capabilities
        if isinstance(capabilities, dict)
        else sync_get_intel_capabilities(executor, logger, vendor_id)
    )


def _resolve_power_command(
    request: GpuSettingsApplyRequest,
    capabilities: JSONDict,
) -> IntelApplyStep | None:
    power_limit = request.power_limit
    if power_limit is None:
        return None
    if is_auto_gpu_setting(power_limit):
        power_caps = read_control_capability_section(capabilities, "power_limit_watts")
        limit_watts = _coerce_capability_int(power_caps, ("default", "max", "current"))
        if limit_watts is None:
            raise StateError("Could not determine default power limit.")
        message = f"Power limit reset to default ({limit_watts}W)."
    else:
        limit_watts = coerce_int_from_numberish(power_limit)
        if limit_watts is None:
            raise StateError("Power limit must be numeric.")
        message = f"Power limit set to {limit_watts}W."
    return IntelApplyStep("power limit", ("--powerlimit", str(limit_watts)), message)


def _resolve_clock_command(
    request: GpuSettingsApplyRequest,
    capabilities: JSONDict,
) -> IntelApplyStep | None:
    if request.core_clock is None and not request.reset_clocks:
        return None
    core_caps = read_control_capability_section(capabilities, "core_clock_mhz")
    if core_caps.get("supported") is not True:
        raise ValidationError("Intel core clock adjustment is unavailable for this GPU.")
    minimum_mhz = _coerce_capability_int(core_caps, ("min",))
    maximum_mhz = _coerce_capability_int(core_caps, ("max",))
    default_mhz = _coerce_capability_int(core_caps, ("default", "max"))
    if minimum_mhz is None or maximum_mhz is None or default_mhz is None:
        raise StateError("Intel core clock capability range is incomplete.")
    if minimum_mhz < 0 or maximum_mhz < 0 or minimum_mhz >= maximum_mhz:
        raise StateError("Intel core clock capability range is invalid.")
    if default_mhz < minimum_mhz or default_mhz > maximum_mhz:
        raise StateError("Intel core clock default is outside the supported range.")
    if request.reset_clocks or is_auto_gpu_setting(request.core_clock):
        target_mhz = default_mhz
        message = f"Core clock range reset to {minimum_mhz}-{target_mhz}MHz."
    else:
        requested_mhz = coerce_int_from_numberish(request.core_clock)
        if requested_mhz is None:
            raise StateError("Core clock must be numeric.")
        target_mhz = min(max(requested_mhz, minimum_mhz), maximum_mhz)
        message = f"Core clock range set to {minimum_mhz}-{target_mhz}MHz."
    return IntelApplyStep(
        "clocks",
        ("-t", "0", "--frequencyrange", f"{minimum_mhz},{target_mhz}"),
        message,
    )


def _coerce_capability_int(caps: JSONDict, keys: tuple[str, ...]) -> int | None:
    for key in keys:
        parsed = coerce_int_from_numberish(caps.get(key))
        if parsed is not None:
            return parsed
    return None
