"""SoAI - Exact NvAPI fan policy topology [backend/hardware/vendors/nvidia/nvapi_fan_controls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError, ValidationError
from core.validation.strict_integer import is_strict_int
from hardware.vendors.nvidia.nvapi_control_observation import NvApiControlObservation
from hardware.vendors.nvidia.nvapi_fan_types import (
    NvApiFanControl,
    NvApiFanStatus,
    NvApiFanStatusEntry,
)
from hardware.vendors.nvidia.nvapi_function_acquisition import (
    require_nvapi_native_success,
    resolve_nvapi_function,
)

if TYPE_CHECKING:
    from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
    from hardware.vendors.nvidia.internal_protocols import NvApiFanControlFunctionProtocol


__all__ = (
    "NvApiFanActuation",
    "NvApiFanMember",
    "read_nvapi_fan_topology",
    "stage_nvapi_fan_control",
    "query_nvapi_fan_controls",
    "read_nvapi_fan_control_member",
    "prepare_nvapi_fan_actuation",
)


@dataclass(frozen=True, slots=True)
class NvApiFanActuation:
    setter: NvApiFanControlFunctionProtocol
    buffer: NvApiFanControl


@dataclass(frozen=True, slots=True)
class NvApiFanMember:
    cooler_id: int
    value: int | None
    mode: int
    minimum: int
    maximum: int


def read_nvapi_fan_topology(
    control: NvApiFanControl, status: NvApiFanStatus
) -> tuple[NvApiFanMember, ...]:
    if not isinstance(control, NvApiFanControl) or not isinstance(status, NvApiFanStatus):
        raise ValidationError("NvAPI fan query buffers are invalid.")
    if control.version != 0x105AC or status.version != 0x106A8:
        raise ValidationError("NvAPI fan query returned an invalid native layout version.")
    if not 1 <= control.count <= 32 or status.count != control.count:
        raise ValidationError("NvAPI fan topology counts are invalid.")
    status_by_id: dict[int, NvApiFanStatusEntry] = {}
    for index in range(status.count):
        status_entry = status.entries[index]
        if status_entry.cooler_id in status_by_id:
            raise ValidationError("NvAPI fan status contains duplicate cooler identities.")
        status_by_id[status_entry.cooler_id] = status_entry
    cooler_ids: set[int] = set()
    members: list[NvApiFanMember] = []
    for index in range(control.count):
        entry = control.entries[index]
        if entry.cooler_id in cooler_ids or entry.cooler_id not in status_by_id:
            raise ValidationError("NvAPI fan cooler relationship is ambiguous or missing.")
        cooler_ids.add(entry.cooler_id)
        observed = status_by_id[entry.cooler_id]
        if entry.mode not in (0, 1):
            raise ValidationError("NvAPI fan control policy is unrecognized.")
        if not 0 <= observed.minimum <= observed.maximum <= 100:
            raise ValidationError("NvAPI fan configured constraints are invalid.")
        value = entry.level if entry.mode == 1 else None
        if value is not None and not observed.minimum <= value <= observed.maximum:
            raise ValidationError("NvAPI manual fan original cannot be restored within its range.")
        members.append(
            NvApiFanMember(entry.cooler_id, value, entry.mode, observed.minimum, observed.maximum)
        )
    return tuple(members)


def stage_nvapi_fan_control(
    control: NvApiFanControl,
    status: NvApiFanStatus,
    *,
    cooler_id: int,
    requested_value: int | None,
    requested_mode: int,
) -> NvApiFanControl:
    if not is_strict_int(cooler_id) or not is_strict_int(requested_mode):
        raise ValidationError("NvAPI fan member identity or requested policy is invalid.")
    if requested_mode not in (0, 1):
        raise ValidationError("NvAPI requested fan policy is unrecognized.")
    if requested_mode == 0 and requested_value is not None:
        raise ValidationError("NvAPI automatic fan policy cannot supply a numeric target.")
    members = read_nvapi_fan_topology(control, status)
    selected: NvApiFanMember | None = None
    selected_index: int | None = None
    for index, member in enumerate(members):
        if member.cooler_id == cooler_id:
            selected = member
            selected_index = index
    if selected is None or selected_index is None:
        raise ValidationError("NvAPI requested fan member is not present in the current topology.")
    if requested_mode == 1 and (
        not is_strict_int(requested_value)
        or not selected.minimum <= requested_value <= selected.maximum
    ):
        raise ValidationError("NvAPI requested fan target is outside its actual range.")
    staged = NvApiFanControl.from_buffer_copy(bytes(control))
    staged.entries[selected_index].mode = requested_mode
    if requested_value is not None:
        staged.entries[selected_index].level = requested_value
    return staged


def query_nvapi_fan_controls(
    handle: ctypes.c_void_p, *, query_interface: Callable[[int], int | None]
) -> tuple[NvApiFanControl, NvApiFanStatus]:
    control_getter = resolve_nvapi_function(
        "NvAPI_GPU_ClientFanCoolersGetControl", query_interface=query_interface
    )
    status_getter = resolve_nvapi_function(
        "NvAPI_GPU_ClientFanCoolersGetStatus", query_interface=query_interface
    )
    if control_getter is None or status_getter is None:
        raise StateError("NvAPI fan original policy or topology facility is unavailable.")
    control, status = NvApiFanControl(), NvApiFanStatus()
    control.version, status.version = 0x105AC, 0x106A8
    require_nvapi_native_success(
        control_getter(handle, ctypes.pointer(control)), actuator_invoked=False
    )
    require_nvapi_native_success(
        status_getter(handle, ctypes.pointer(status)), actuator_invoked=False
    )
    read_nvapi_fan_topology(control, status)
    return control, status


def read_nvapi_fan_control_member(
    handle: ctypes.c_void_p,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
    *,
    query_interface: Callable[[int], int | None],
    goal: Literal["requested", "original"],
) -> NvApiControlObservation:
    control, status = query_nvapi_fan_controls(handle, query_interface=query_interface)
    return _fan_observation(control, status, member, record, goal)


def _fan_observation(
    control: NvApiFanControl,
    status: NvApiFanStatus,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
    goal: Literal["requested", "original"],
) -> NvApiControlObservation:
    if goal not in ("requested", "original"):
        raise ValidationError("NvAPI fan readback goal is invalid.")
    fans = read_nvapi_fan_topology(control, status)
    keys = {f"cooler:{fan.cooler_id}" for fan in fans}
    frozen_keys = {
        row.member_id
        for row in record.members
        if row.backend == "nvapi" and row.field == "fan_speed"
    }
    if (
        keys != frozen_keys
        or (member.backend, member.field, member.native_unit) != ("nvapi", "fan_speed", "%")
        or member.domain_id is not None
        or member.pstate_id is not None
    ):
        raise ValidationError("NvAPI frozen fan routing or complete physical fan coverage changed.")
    fan = next((row for row in fans if f"cooler:{row.cooler_id}" == member.member_id), None)
    if fan is None or record.requested_units[member.field] != "%":
        raise ValidationError("NvAPI fan member or user unit is invalid.")
    desired_value, desired_mode = (
        (member.original_value, member.original_mode)
        if goal == "original"
        else (member.requested_value, member.requested_mode)
    )
    if not is_strict_int(desired_mode) or not is_strict_int(member.original_mode):
        raise ValidationError("NvAPI frozen fan policy must be a native integer.")
    valid_target = desired_mode == 0 and desired_value is None
    if desired_mode == 1:
        valid_target = is_strict_int(desired_value) and fan.minimum <= desired_value <= fan.maximum
    restorable = member.original_mode == 0 and member.original_value is None
    if member.original_mode == 1:
        restorable = (
            is_strict_int(member.original_value)
            and fan.minimum <= member.original_value <= fan.maximum
        )
    return NvApiControlObservation(fan.value, fan.mode, valid_target, restorable, None)


def prepare_nvapi_fan_actuation(
    handle: ctypes.c_void_p,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
    *,
    query_interface: Callable[[int], int | None],
    goal: Literal["requested", "original"],
    purpose: Literal["observe", "stage"],
) -> tuple[NvApiControlObservation, NvApiFanActuation | None]:
    if purpose not in ("observe", "stage"):
        raise ValidationError("NvAPI native query purpose is invalid.")
    observed = read_nvapi_fan_control_member(
        handle, member, record, query_interface=query_interface, goal=goal
    )
    if purpose == "observe":
        return observed, None
    if not observed.user_meaning_verified or not observed.original_restorable:
        return observed, None
    control, status = query_nvapi_fan_controls(handle, query_interface=query_interface)
    frozen_fans = tuple(
        row for row in record.members if row.backend == "nvapi" and row.field == "fan_speed"
    )
    observations = tuple(
        _fan_observation(control, status, row, record, goal) for row in frozen_fans
    )
    if all(
        (current.value, current.mode)
        == (
            (row.original_value, row.original_mode)
            if goal == "original"
            else (row.requested_value, row.requested_mode)
        )
        for row, current in zip(frozen_fans, observations, strict=True)
    ):
        return observed, None
    setter = resolve_nvapi_function(
        "NvAPI_GPU_ClientFanCoolersSetControl", query_interface=query_interface
    )
    if setter is None:
        raise StateError("NvAPI selected fan actuator is unavailable.")
    control, status = query_nvapi_fan_controls(handle, query_interface=query_interface)
    observed = _fan_observation(control, status, member, record, goal)
    observations = tuple(
        _fan_observation(control, status, row, record, goal) for row in frozen_fans
    )
    staged = control
    for frozen, current in zip(frozen_fans, observations, strict=True):
        if not current.user_meaning_verified or not current.original_restorable:
            return observed, None
        if goal == "requested" and (current.value, current.mode) != (
            frozen.original_value,
            frozen.original_mode,
        ):
            raise StateError("NvAPI full fan buffer original authority changed.")
        frozen_value, frozen_mode = (
            (frozen.original_value, frozen.original_mode)
            if goal == "original"
            else (frozen.requested_value, frozen.requested_mode)
        )
        if not is_strict_int(frozen_mode):
            raise ValidationError("NvAPI frozen full fan policy is invalid.")
        fan_id = next(
            row.cooler_id
            for row in read_nvapi_fan_topology(control, status)
            if f"cooler:{row.cooler_id}" == frozen.member_id
        )
        if frozen_value is not None and not is_strict_int(frozen_value):
            raise ValidationError("NvAPI frozen full fan target is invalid.")
        staged = stage_nvapi_fan_control(
            staged,
            status,
            cooler_id=fan_id,
            requested_value=frozen_value,
            requested_mode=frozen_mode,
        )
    return observed, NvApiFanActuation(setter, staged)
