"""SoAI - Unique actual NvAPI power policy relation [backend/hardware/vendors/nvidia/nvapi_power_controls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError, ValidationError
from core.validation.strict_integer import is_strict_int
from core.validation.strict_numbers import require_positive_int_strict
from hardware.vendors.nvidia.nvapi_control_observation import NvApiControlObservation
from hardware.vendors.nvidia.nvapi_function_acquisition import (
    require_nvapi_native_success,
    resolve_nvapi_function,
)
from hardware.vendors.nvidia.nvapi_power_types import NvApiPowerInfo, NvApiPowerStatus
from hardware.vendors.nvidia.nvml_physical_binding import acquire_nvml_physical_binding

if TYPE_CHECKING:
    from core.hardware.gpu_physical_identity import GPUPhysicalDevice
    from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
    from hardware.vendors.nvidia.internal_protocols import (
        NvApiPowerStatusFunctionProtocol,
        NvmlControlModuleProtocol,
    )


__all__ = (
    "NvApiPowerActuation",
    "NvApiPowerMember",
    "read_nvapi_power_member",
    "stage_nvapi_power_control",
    "query_nvapi_power_controls",
    "read_nvapi_power_conversion",
    "prepare_nvapi_power_actuation",
)


@dataclass(frozen=True, slots=True)
class NvApiPowerActuation:
    setter: NvApiPowerStatusFunctionProtocol
    buffer: NvApiPowerStatus


@dataclass(frozen=True, slots=True)
class NvApiPowerMember:
    pstate: int
    value: int
    minimum: int
    default: int
    maximum: int


def read_nvapi_power_member(info: NvApiPowerInfo, status: NvApiPowerStatus) -> NvApiPowerMember:
    if not isinstance(info, NvApiPowerInfo) or not isinstance(status, NvApiPowerStatus):
        raise ValidationError("NvAPI power query buffers are invalid.")
    if info.version != 0x100B8 or status.version != 0x10048:
        raise ValidationError("NvAPI power query returned an invalid native layout version.")
    if (
        info.valid != 1
        or not 1 <= info.count <= 4
        or not 1 <= status.count <= 4
        or info.count != status.count
    ):
        raise ValidationError("NvAPI power policy availability or counts are invalid.")
    if info.count != 1:
        raise StateError(
            "NvAPI power status relationship to multiple policy members is unproved.",
            details={"reason": "power_policy_relationship_unproved"},
        )
    policy = info.entries[0]
    observed = status.entries[0]
    if not 0 <= policy.pstate <= 15:
        raise ValidationError("NvAPI power policy Pstate identity is invalid.")
    if not policy.minimum <= policy.default <= policy.maximum:
        raise ValidationError("NvAPI power policy default or native range is invalid.")
    if not policy.minimum <= observed.power <= policy.maximum:
        raise ValidationError("NvAPI original power policy cannot be restored in its actual range.")
    return NvApiPowerMember(
        policy.pstate, observed.power, policy.minimum, policy.default, policy.maximum
    )


def stage_nvapi_power_control(
    info: NvApiPowerInfo,
    status: NvApiPowerStatus,
    *,
    pstate: int,
    requested_power: int,
) -> NvApiPowerStatus:
    member = read_nvapi_power_member(info, status)
    if not is_strict_int(pstate) or pstate != member.pstate:
        raise ValidationError("NvAPI requested power policy relation changed or is invalid.")
    if (
        not is_strict_int(requested_power)
        or not member.minimum <= requested_power <= member.maximum
    ):
        raise ValidationError("NvAPI requested power policy target is outside its actual range.")
    staged = NvApiPowerStatus.from_buffer_copy(bytes(status))
    staged.entries[0].power = requested_power
    return staged


def query_nvapi_power_controls(
    handle: ctypes.c_void_p, *, query_interface: Callable[[int], int | None]
) -> tuple[NvApiPowerInfo, NvApiPowerStatus]:
    policy_getter = resolve_nvapi_function(
        "NvAPI_GPU_ClientPowerPoliciesGetInfo", query_interface=query_interface
    )
    power_getter = resolve_nvapi_function(
        "NvAPI_GPU_ClientPowerPoliciesGetStatus", query_interface=query_interface
    )
    if policy_getter is None or power_getter is None:
        raise StateError("NvAPI power original or native policy facility is unavailable.")
    info, status = NvApiPowerInfo(), NvApiPowerStatus()
    info.version, status.version = 0x100B8, 0x10048
    require_nvapi_native_success(
        policy_getter(handle, ctypes.pointer(info)), actuator_invoked=False
    )
    require_nvapi_native_success(
        power_getter(handle, ctypes.pointer(status)), actuator_invoked=False
    )
    read_nvapi_power_member(info, status)
    return info, status


def read_nvapi_power_conversion(
    module: NvmlControlModuleProtocol | None, target: GPUPhysicalDevice
) -> int:
    if module is None:
        raise StateError("NvAPI absolute watts require an actual native default-watt authority.")
    try:
        native_bound = acquire_nvml_physical_binding(module, target=target)
        return require_positive_int_strict(
            module.nvmlDeviceGetPowerManagementDefaultLimit(native_bound.handle),
            error_message="NvAPI native default power conversion is invalid.",
        )
    except module.NVMLError as exception:
        raise StateError(
            "NvAPI native default-watt authority could not be queried.", cause=exception
        ) from exception


def _power_observation(
    info: NvApiPowerInfo,
    status: NvApiPowerStatus,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
    target: GPUPhysicalDevice,
    module: NvmlControlModuleProtocol | None,
    goal: Literal["requested", "original"],
) -> NvApiControlObservation:
    if goal not in ("requested", "original"):
        raise ValidationError("NvAPI power readback goal is invalid.")
    power = read_nvapi_power_member(info, status)
    if (
        (
            member.backend,
            member.field,
            member.member_id,
            member.native_unit,
            member.domain_id,
            member.pstate_id,
        )
        != ("nvapi", "power_limit", "policy", "milli-percent", None, power.pstate)
        or member.original_mode is not None
        or member.requested_mode is not None
        or record.requested_units[member.field] != "W"
    ):
        raise ValidationError("NvAPI frozen power routing or unit is invalid.")
    desired = member.original_value if goal == "original" else member.requested_value
    restorable = (
        is_strict_int(member.original_value)
        and power.minimum <= member.original_value <= power.maximum
    )
    verified = is_strict_int(desired) and power.minimum <= desired <= power.maximum
    failure = None
    if verified and goal == "requested":
        if record.requested_modes[member.field] == "auto":
            verified = desired == power.default
        elif record.requested_modes[member.field] == "manual":
            watts = record.requested_settings[member.field]
            if not is_strict_int(watts) or watts <= 0:
                raise ValidationError("NvAPI frozen user watts are invalid.")
            if power.default != 100000:
                verified = False
                failure = StateError(
                    "NvAPI absolute-watt reference for this native default is unproved."
                )
            else:
                try:
                    default_mw = read_nvapi_power_conversion(module, target)
                except StateError as exception:
                    verified, failure = False, exception
                else:
                    verified = (
                        is_strict_int(desired) and desired * default_mw == watts * 100_000_000
                    )
        else:
            raise ValidationError("NvAPI frozen user power mode is invalid.")
    return NvApiControlObservation(power.value, None, verified, restorable, failure)


def prepare_nvapi_power_actuation(
    handle: ctypes.c_void_p,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
    *,
    query_interface: Callable[[int], int | None],
    target: GPUPhysicalDevice,
    module: NvmlControlModuleProtocol | None,
    goal: Literal["requested", "original"],
    purpose: Literal["observe", "stage"],
) -> tuple[NvApiControlObservation, NvApiPowerActuation | None]:
    if purpose not in ("observe", "stage"):
        raise ValidationError("NvAPI native query purpose is invalid.")
    info, status = query_nvapi_power_controls(handle, query_interface=query_interface)
    observed = _power_observation(info, status, member, record, target, module, goal)
    if purpose == "observe":
        return observed, None
    desired = member.original_value if goal == "original" else member.requested_value
    if not observed.requires_actuation(desired, None):
        return observed, None
    setter = resolve_nvapi_function(
        "NvAPI_GPU_ClientPowerPoliciesSetStatus", query_interface=query_interface
    )
    if setter is None:
        raise StateError("NvAPI selected power actuator is unavailable.")
    info, status = query_nvapi_power_controls(handle, query_interface=query_interface)
    observed = _power_observation(info, status, member, record, target, module, goal)
    if not observed.user_meaning_verified or not observed.original_restorable:
        return observed, None
    if not is_strict_int(desired) or member.pstate_id is None:
        raise ValidationError("NvAPI frozen native power target is invalid.")
    return observed, NvApiPowerActuation(
        setter,
        stage_nvapi_power_control(info, status, pstate=member.pstate_id, requested_power=desired),
    )
