"""SoAI - Selected NVML actuator and original restoration acquisition [backend/hardware/vendors/nvidia/nvml_actuator_acquisition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_recovery_records import GPURecoveryMember
from hardware.vendors.nvidia.internal_protocols import (
    NvmlControlModuleProtocol,
    NvmlNativeFunctionResolverProtocol,
)
from hardware.vendors.nvidia.nvml_clock_offset_abi import set_clock_offset
from hardware.vendors.nvidia.tuning_nvml import invoke_nvml_persistence_member
from hardware.vendors.nvidia.tuning_nvml_clock_offsets import invoke_nvml_legacy_clock_member
from hardware.vendors.nvidia.tuning_nvml_controls import invoke_nvml_fan_member
from hardware.vendors.nvidia.tuning_power_limit import invoke_nvml_power_member

if TYPE_CHECKING:
    from hardware.vendors.nvidia.internal_protocols import NvmlDeviceHandle


__all__ = (
    "require_nvml_member_actuators",
    "invoke_nvml_member_actuator",
)


def require_nvml_member_actuators(
    member: GPURecoveryMember,
    resolver: NvmlNativeFunctionResolverProtocol | None,
    native_error: type[Exception],
    *,
    goal: Literal["requested", "original"],
) -> None:
    if member.backend != "nvml":
        raise ValidationError("NVML actuator acquisition requires an actual NVML member.")
    if goal not in ("requested", "original"):
        raise ValidationError("NVML actuator acquisition requires an explicit goal.")
    if (
        goal == "requested"
        and member.original_value == member.requested_value
        and member.original_mode == member.requested_mode
    ):
        return
    if resolver is None:
        raise StateError("NVML selected native function resolver is unavailable.")
    try:
        if member.field == "power_limit":
            if not callable(resolver("nvmlDeviceSetPowerManagementLimit")):
                raise StateError("NVML selected power actuator is malformed.")
        elif member.field == "persistence_mode":
            if not callable(resolver("nvmlDeviceSetPersistenceMode")):
                raise StateError("NVML selected persistence actuator is malformed.")
        elif member.field == "fan_speed" and goal == "original":
            if member.original_mode == 0:
                if not callable(resolver("nvmlDeviceSetDefaultFanSpeed_v2")):
                    raise StateError("NVML original automatic fan actuator is malformed.")
            elif member.original_mode == 1:
                if not callable(resolver("nvmlDeviceSetFanSpeed_v2")):
                    raise StateError("NVML original manual fan actuator is malformed.")
            else:
                raise ValidationError("NVML original fan policy route is invalid.")
        elif member.field == "fan_speed":
            if member.requested_mode not in (0, 1) or member.original_mode not in (0, 1):
                raise ValidationError("NVML selected fan policy route is invalid.")
            if member.requested_mode == 1:
                if not callable(resolver("nvmlDeviceSetFanSpeed_v2")):
                    raise StateError("NVML selected manual fan actuator is malformed.")
                if member.original_mode == 0 and not callable(
                    resolver("nvmlDeviceSetDefaultFanSpeed_v2")
                ):
                    raise StateError("NVML original automatic fan restoration is malformed.")
            else:
                if not callable(resolver("nvmlDeviceSetDefaultFanSpeed_v2")):
                    raise StateError("NVML selected automatic fan actuator is malformed.")
                if member.original_mode == 1 and not callable(resolver("nvmlDeviceSetFanSpeed_v2")):
                    raise StateError("NVML original manual fan restoration is malformed.")
        elif member.member_id == "application_clocks":
            if not callable(resolver("nvmlDeviceSetApplicationsClocks")):
                raise StateError("NVML paired application-clock actuator is malformed.")
        elif member.member_id == "vf_offset:modern":
            if not callable(resolver("nvmlDeviceSetClockOffsets")):
                raise StateError("NVML selected modern clock actuator is malformed.")
        elif member.member_id == "vf_offset:legacy" and member.domain_id == 0:
            if not callable(resolver("nvmlDeviceSetGpcClkVfOffset")):
                raise StateError("NVML selected graphics clock actuator is malformed.")
        elif member.member_id == "vf_offset:legacy" and member.domain_id == 2:
            if not callable(resolver("nvmlDeviceSetMemClkVfOffset")):
                raise StateError("NVML selected memory clock actuator is malformed.")
        else:
            raise ValidationError("NVML selected actuator has no proved native route.")
    except (native_error, ctypes.ArgumentError) as exception:
        raise StateError(
            "NVML selected native actuator acquisition failed before invocation.",
            details={"actuator_invoked": False, "field": member.field},
            cause=exception,
        ) from exception


def invoke_nvml_member_actuator(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    member: GPURecoveryMember,
    resolver: NvmlNativeFunctionResolverProtocol | None,
    goal: Literal["requested", "original"],
) -> None:
    value, mode = (
        (member.original_value, member.original_mode)
        if goal == "original"
        else (member.requested_value, member.requested_mode)
    )
    if member.field == "power_limit":
        invoke_nvml_power_member(module, handle, native_value=value)
    elif member.field == "fan_speed":
        invoke_nvml_fan_member(module, handle, member, native_value=value, native_mode=mode)
    elif member.field == "persistence_mode":
        invoke_nvml_persistence_member(module, handle, native_mode=mode)
    elif member.member_id == "vf_offset:legacy":
        invoke_nvml_legacy_clock_member(module, handle, member, native_value=value)
    elif (
        member.member_id == "vf_offset:modern"
        and member.domain_id is not None
        and resolver is not None
    ):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValidationError("NVML frozen modern clock target is invalid.")
        set_clock_offset(
            handle=handle,
            clock_type=member.domain_id,
            pstate=0,
            offset_mhz=value,
            resolve_function=resolver,
            native_error=module.NVMLError,
        )
    else:
        raise StateError("NVML prepared native actuator is unavailable.")
