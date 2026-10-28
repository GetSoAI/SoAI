"""SoAI - NvAPI selected physical acquisition and native member observations [backend/hardware/vendors/nvidia/nvapi_control_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable
from typing import Literal

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.system.privileges import is_admin
from core.system.protocols import CommandExecutorProtocol
from hardware.gpu_inventory.executable_resolution import GpuExecutableResolution
from hardware.vendors.nvidia.internal_protocols import (
    NvmlControlModuleProtocol,
)
from hardware.vendors.nvidia.nvapi_clock_controls import (
    NvApiClockActuation,
    prepare_nvapi_clock_actuation,
)
from hardware.vendors.nvidia.nvapi_control_observation import NvApiControlObservation
from hardware.vendors.nvidia.nvapi_fan_controls import (
    NvApiFanActuation,
    prepare_nvapi_fan_actuation,
)
from hardware.vendors.nvidia.nvapi_function_acquisition import resolve_nvapi_function
from hardware.vendors.nvidia.nvapi_physical_binding import (
    NvApiBoundDevice,
    acquire_nvapi_physical_binding,
)
from hardware.vendors.nvidia.nvapi_power_controls import (
    NvApiPowerActuation,
    prepare_nvapi_power_actuation,
)

__all__ = (
    "prepare_nvapi_member_invocation",
    "acquire_nvapi_control_binding",
    "nvapi_member_is_safe",
    "nvapi_member_goal_matches",
    "nvapi_clock_readiness_recheck",
)


def prepare_nvapi_member_invocation(
    executor: CommandExecutorProtocol,
    record: GPURecoveryRecord,
    target: GPUPhysicalDevice,
    member: GPURecoveryMember,
    *,
    executable: GpuExecutableResolution,
    query_interface: Callable[[int], int | None],
    nvml_module: NvmlControlModuleProtocol | None,
    goal: Literal["requested", "original"],
    purpose: Literal["observe", "stage"],
) -> tuple[
    ctypes.c_void_p,
    NvApiControlObservation,
    NvApiFanActuation | NvApiClockActuation | NvApiPowerActuation | None,
]:
    if purpose == "stage" and is_admin() is not True:
        raise StateError("NvAPI control requires administrator privileges.")
    bound = acquire_nvapi_control_binding(
        executor, target=target, executable=executable, query_interface=query_interface
    )
    if member.field == "fan_speed":
        observed, fan_action = prepare_nvapi_fan_actuation(
            bound.handle,
            member,
            record,
            query_interface=query_interface,
            goal=goal,
            purpose=purpose,
        )
        return bound.handle, observed, fan_action
    if member.field in ("core_clock", "mem_clock"):
        observed, clock_action = prepare_nvapi_clock_actuation(
            bound.handle,
            member,
            record,
            query_interface=query_interface,
            target=bound.device,
            module=nvml_module,
            goal=goal,
            purpose=purpose,
            readiness_recheck=nvapi_clock_readiness_recheck(
                executor, bound, executable=executable, query_interface=query_interface
            ),
        )
        return bound.handle, observed, clock_action
    if member.field == "power_limit":
        observed, power_action = prepare_nvapi_power_actuation(
            bound.handle,
            member,
            record,
            query_interface=query_interface,
            target=bound.device,
            module=nvml_module,
            goal=goal,
            purpose=purpose,
        )
        return bound.handle, observed, power_action
    raise ValidationError("NvAPI member has no declared native control owner.")


def acquire_nvapi_control_binding(
    executor: CommandExecutorProtocol,
    *,
    target: GPUPhysicalDevice,
    executable: GpuExecutableResolution,
    query_interface: Callable[[int], int | None],
) -> NvApiBoundDevice:
    enum_gpus = resolve_nvapi_function("NvAPI_EnumPhysicalGPUs", query_interface=query_interface)
    bus_query = resolve_nvapi_function("NvAPI_GPU_GetBusId", query_interface=query_interface)
    if enum_gpus is None or bus_query is None:
        raise StateError("NvAPI physical enumeration or bus query facility is unavailable.")
    return acquire_nvapi_physical_binding(
        executor,
        target=target,
        executable=executable,
        enumerate_gpus=enum_gpus,
        read_bus=bus_query,
        read_slot=resolve_nvapi_function("NvAPI_GPU_GetBusSlotId", query_interface=query_interface),
    )


def nvapi_member_is_safe(
    member: GPURecoveryMember,
    observed: NvApiControlObservation,
    goal: Literal["requested", "original"],
) -> bool:
    return (
        observed.user_meaning_verified
        and observed.original_restorable
        and (
            goal == "original"
            or (observed.value, observed.mode) == (member.original_value, member.original_mode)
        )
    )


def nvapi_member_goal_matches(
    member: GPURecoveryMember,
    observed: NvApiControlObservation,
    goal: Literal["requested", "original"],
) -> bool:
    desired = (
        (member.original_value, member.original_mode)
        if goal == "original"
        else (member.requested_value, member.requested_mode)
    )
    return observed.user_meaning_verified and (observed.value, observed.mode) == desired


def nvapi_clock_readiness_recheck(
    executor: CommandExecutorProtocol,
    bound: NvApiBoundDevice,
    *,
    executable: GpuExecutableResolution,
    query_interface: Callable[[int], int | None],
) -> Callable[[], None]:
    attempted = False

    def recheck() -> None:
        nonlocal attempted
        if attempted:
            raise StateError("NvAPI bounded clock readiness recheck is exhausted.")
        attempted = True
        refreshed = acquire_nvapi_control_binding(
            executor, target=bound.device, executable=executable, query_interface=query_interface
        )
        if refreshed.device != bound.device or refreshed.handle.value != bound.handle.value:
            raise StateError("NvAPI selected physical handle changed during clock readiness.")

    return recheck
