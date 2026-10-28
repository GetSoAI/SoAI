"""SoAI - Exact NvAPI Pstate clock member relations [backend/hardware/vendors/nvidia/nvapi_clock_controls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError, ValidationError
from core.validation.strict_integer import is_strict_int
from hardware.vendors.nvidia.nvapi_control_observation import NvApiControlObservation
from hardware.vendors.nvidia.nvapi_function_acquisition import (
    require_nvapi_native_success,
    resolve_nvapi_function,
)
from hardware.vendors.nvidia.nvapi_native_types import NvApiClockEntry, NvApiPstate, NvApiPstates
from hardware.vendors.nvidia.nvml_clock_observations import read_nvml_clock_baseline
from hardware.vendors.nvidia.nvml_physical_binding import acquire_nvml_physical_binding

if TYPE_CHECKING:
    from core.hardware.gpu_physical_identity import GPUPhysicalDevice
    from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
    from hardware.vendors.nvidia.internal_protocols import (
        NvApiPstatesFunctionProtocol,
        NvmlControlModuleProtocol,
    )


__all__ = (
    "NvApiClockActuation",
    "NvApiClockMember",
    "read_nvapi_clock_member",
    "stage_nvapi_clock_control",
    "query_nvapi_clock_controls",
    "read_nvapi_clock_conversion",
    "prepare_nvapi_clock_actuation",
)


@dataclass(frozen=True, slots=True)
class NvApiClockActuation:
    setter: NvApiPstatesFunctionProtocol
    buffer: NvApiPstates


@dataclass(frozen=True, slots=True)
class NvApiClockMember:
    pstate: int
    domain: int
    value: int
    minimum: int
    maximum: int
    data_type: int
    frequency: int | None
    minimum_frequency: int | None
    maximum_frequency: int | None


def read_nvapi_clock_member(info: NvApiPstates, *, pstate: int, domain: int) -> NvApiClockMember:
    if not is_strict_int(pstate) or not 0 <= pstate <= 15 or not is_strict_int(domain):
        raise ValidationError("NvAPI requested clock routing is invalid.")
    if domain not in (0, 4):
        raise ValidationError("NvAPI requested clock domain is unsupported.")
    if not isinstance(info, NvApiPstates) or info.version != 0x11C94:
        raise ValidationError("NvAPI Pstate query returned an invalid native layout version.")
    if (
        not 1 <= info.pstate_count <= 16
        or not 1 <= info.clock_count <= 8
        or not 0 <= info.voltage_count <= 4
    ):
        raise ValidationError("NvAPI Pstate query counts are invalid.")
    if info.editable & 1 != 1:
        raise ValidationError("NvAPI queried Pstate controls are not editable.")
    selected_state: NvApiPstate | None = None
    states: set[int] = set()
    for index in range(info.pstate_count):
        state = info.pstates[index]
        if not 0 <= state.pstate <= 15 or state.pstate in states:
            raise ValidationError("NvAPI queried Pstate identities are invalid or ambiguous.")
        states.add(state.pstate)
        if state.pstate == pstate:
            selected_state = state
    if selected_state is None or selected_state.editable & 1 != 1:
        raise ValidationError("NvAPI requested Pstate is unavailable or not editable.")
    selected_clock: NvApiClockEntry | None = None
    domains: set[int] = set()
    for index in range(info.clock_count):
        clock = selected_state.clocks[index]
        if clock.domain in domains:
            raise ValidationError("NvAPI Pstate clock domain relationship is ambiguous.")
        domains.add(clock.domain)
        if clock.domain == domain:
            selected_clock = clock
    if selected_clock is None or selected_clock.editable & 1 != 1:
        raise ValidationError("NvAPI requested clock domain is unavailable or not editable.")
    delta = selected_clock.delta
    if delta.minimum > delta.maximum or not delta.minimum <= delta.value <= delta.maximum:
        raise ValidationError("NvAPI original clock delta is outside its actual restore range.")
    if selected_clock.type not in (0, 1):
        raise ValidationError("NvAPI queried clock data type is unrecognized.")
    frequency = selected_clock.data.frequency if selected_clock.type == 0 else None
    minimum_frequency = (
        selected_clock.data.range.minimum_frequency if selected_clock.type == 1 else None
    )
    maximum_frequency = (
        selected_clock.data.range.maximum_frequency if selected_clock.type == 1 else None
    )
    return NvApiClockMember(
        pstate,
        domain,
        delta.value,
        delta.minimum,
        delta.maximum,
        selected_clock.type,
        frequency,
        minimum_frequency,
        maximum_frequency,
    )


def stage_nvapi_clock_control(
    info: NvApiPstates, *, pstate: int, domain: int, requested_delta: int
) -> NvApiPstates:
    member = read_nvapi_clock_member(info, pstate=pstate, domain=domain)
    if (
        not is_strict_int(requested_delta)
        or not member.minimum <= requested_delta <= member.maximum
    ):
        raise ValidationError("NvAPI requested clock delta is outside its actual native range.")
    staged = NvApiPstates()
    staged.version = 0x11C94
    staged.pstate_count = 1
    staged.clock_count = 1
    staged.voltage_count = 0
    staged.pstates[0].pstate = pstate
    staged.pstates[0].clocks[0].domain = domain
    staged.pstates[0].clocks[0].type = 0
    staged.pstates[0].clocks[0].delta.value = requested_delta
    return staged


def query_nvapi_clock_controls(
    handle: ctypes.c_void_p,
    *,
    query_interface: Callable[[int], int | None],
    readiness_recheck: Callable[[], None] | None = None,
) -> NvApiPstates:
    clock_getter = resolve_nvapi_function("NvAPI_GPU_GetPstates20", query_interface=query_interface)
    if clock_getter is None:
        raise StateError("NvAPI Pstate original query facility is unavailable.")
    info = NvApiPstates()
    info.version = 0x11C94
    status = clock_getter(handle, ctypes.pointer(info))
    if is_strict_int(status) and status == -1 and readiness_recheck is not None:
        readiness_recheck()
        info = NvApiPstates()
        info.version = 0x11C94
        status = clock_getter(handle, ctypes.pointer(info))
    require_nvapi_native_success(status, actuator_invoked=False)
    return info


def read_nvapi_clock_conversion(
    module: NvmlControlModuleProtocol | None, target: GPUPhysicalDevice, domain: int
) -> int:
    if domain == 4:
        raise StateError("NvAPI memory absolute clock conversion is unproved.")
    if module is None:
        raise StateError("NvAPI absolute clocks require an actual native P0 baseline authority.")
    if domain != 0:
        raise ValidationError("NvAPI conversion domain is invalid.")
    try:
        native_bound = acquire_nvml_physical_binding(module, target=target)
        return read_nvml_clock_baseline(module, native_bound.handle, 0)
    except module.NVMLError as exception:
        raise StateError(
            "NvAPI native P0 clock authority could not be queried.", cause=exception
        ) from exception


def _clock_observation(
    info: NvApiPstates,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
    target: GPUPhysicalDevice,
    module: NvmlControlModuleProtocol | None,
    goal: Literal["requested", "original"],
) -> NvApiControlObservation:
    domain = 0 if member.field == "core_clock" else 4
    if goal not in ("requested", "original") or member.field not in ("core_clock", "mem_clock"):
        raise ValidationError("NvAPI clock readback goal or field is invalid.")
    if (
        (member.backend, member.member_id, member.native_unit, member.domain_id, member.pstate_id)
        != ("nvapi", "pstate_delta", "kHz", domain, 0)
        or member.original_mode is not None
        or member.requested_mode is not None
        or record.requested_units[member.field] != "MHz"
    ):
        raise ValidationError("NvAPI frozen clock routing or unit is invalid.")
    clock = read_nvapi_clock_member(info, pstate=0, domain=domain)
    desired = member.original_value if goal == "original" else member.requested_value
    restorable = (
        is_strict_int(member.original_value)
        and clock.minimum <= member.original_value <= clock.maximum
    )
    verified = is_strict_int(desired) and clock.minimum <= desired <= clock.maximum
    failure = None
    if verified and goal == "requested":
        if record.requested_modes[member.field] == "auto":
            verified = desired == 0
        elif record.requested_modes[member.field] == "manual":
            user_mhz = record.requested_settings[member.field]
            if not is_strict_int(user_mhz) or user_mhz <= 0:
                raise ValidationError("NvAPI frozen user clock is invalid.")
            try:
                baseline = read_nvapi_clock_conversion(module, target, domain)
            except StateError as exception:
                verified, failure = False, exception
            else:
                verified = desired == (user_mhz - baseline) * 1000
        else:
            raise ValidationError("NvAPI frozen user clock mode is invalid.")
    return NvApiControlObservation(clock.value, None, verified, restorable, failure)


def prepare_nvapi_clock_actuation(
    handle: ctypes.c_void_p,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
    *,
    query_interface: Callable[[int], int | None],
    target: GPUPhysicalDevice,
    module: NvmlControlModuleProtocol | None,
    goal: Literal["requested", "original"],
    purpose: Literal["observe", "stage"],
    readiness_recheck: Callable[[], None] | None = None,
) -> tuple[NvApiControlObservation, NvApiClockActuation | None]:
    if purpose not in ("observe", "stage"):
        raise ValidationError("NvAPI native query purpose is invalid.")
    info = query_nvapi_clock_controls(
        handle, query_interface=query_interface, readiness_recheck=readiness_recheck
    )
    observed = _clock_observation(info, member, record, target, module, goal)
    if purpose == "observe":
        return observed, None
    desired = member.original_value if goal == "original" else member.requested_value
    if not observed.requires_actuation(desired, None):
        return observed, None
    setter = resolve_nvapi_function("NvAPI_GPU_SetPstates20", query_interface=query_interface)
    if setter is None:
        raise StateError("NvAPI selected clock actuator is unavailable.")
    info = query_nvapi_clock_controls(
        handle, query_interface=query_interface, readiness_recheck=readiness_recheck
    )
    observed = _clock_observation(info, member, record, target, module, goal)
    if not observed.user_meaning_verified or not observed.original_restorable:
        return observed, None
    if not is_strict_int(desired) or member.domain_id is None:
        raise ValidationError("NvAPI frozen native clock target is invalid.")
    return observed, NvApiClockActuation(
        setter,
        stage_nvapi_clock_control(info, pstate=0, domain=member.domain_id, requested_delta=desired),
    )
