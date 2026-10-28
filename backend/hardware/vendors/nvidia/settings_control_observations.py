"""SoAI - Fresh NVIDIA settings topology, originals and conversion observations [backend/hardware/vendors/nvidia/settings_control_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_control_types import NativeMemberObservation
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.validation.strict_integer import is_strict_int
from core.validation.strict_numbers import require_int_in_range_strict, require_positive_int_strict
from hardware.vendors.nvidia.settings_control_queries import (
    NvidiaSettingsSession,
    parse_settings_attribute,
    query_settings_fans,
    query_settings_output,
    query_settings_performance_modes,
)
from hardware.vendors.nvidia.settings_physical_binding import acquire_settings_physical_binding

__all__ = (
    "SettingsMemberState",
    "read_settings_member_state",
)


@dataclass(frozen=True, slots=True)
class SettingsMemberState:
    observation: NativeMemberObservation
    safe: bool
    target: str
    native_target: int | None


def read_settings_member_state(
    session: NvidiaSettingsSession,
    record: GPURecoveryRecord,
    target: GPUPhysicalDevice,
    member: GPURecoveryMember,
    *,
    goal: Literal["requested", "original"],
    stage: bool,
) -> SettingsMemberState:
    if member.backend != "nvidia_settings" or goal not in ("requested", "original"):
        raise ValidationError("NVIDIA settings member requires its explicit native route and goal.")
    native_id = acquire_settings_physical_binding(session, target=target).native_gpu_id
    value, mode = (
        (member.original_value, member.original_mode)
        if goal == "original"
        else (member.requested_value, member.requested_mode)
    )
    if member.member_id == "gpu_fan_policy":
        if (
            (member.native_unit, member.domain_id, member.pstate_id) != ("policy", None, None)
            or value is not None
            or not is_strict_int(mode)
            or mode not in (0, 1)
        ):
            raise ValidationError("NVIDIA settings frozen fan policy is invalid.")
        attribute_target = f"[gpu:{native_id}]/GPUFanControlState"
        current = parse_settings_attribute(
            query_settings_output(session, attribute_target),
            attribute="GPUFanControlState",
            target_type="gpu",
            target_id=native_id,
        ).value
        if current not in (0, 1):
            raise ValidationError("NVIDIA settings actual fan policy is invalid.")
        return SettingsMemberState(
            NativeMemberObservation(None, current, current == mode),
            goal == "original" or current == member.original_mode,
            attribute_target,
            mode,
        )
    if member.field == "fan_speed":
        suffix = member.member_id.removeprefix("fan:")
        if not suffix.isascii() or not suffix.isdigit() or member.member_id != f"fan:{int(suffix)}":
            raise ValidationError("NVIDIA settings frozen fan identity is invalid.")
        if (
            (member.native_unit, member.domain_id, member.pstate_id) != ("%", None, None)
            or not is_strict_int(mode)
            or mode not in (0, 1)
        ):
            raise ValidationError("NVIDIA settings frozen fan relation is invalid.")
        fans = query_settings_fans(session, native_gpu_id=native_id)
        expected_fans = {
            item.member_id
            for item in record.members
            if item.backend == "nvidia_settings"
            and item.field == "fan_speed"
            and item.member_id.startswith("fan:")
        }
        if expected_fans != {f"fan:{fan.native_fan_id}" for fan in fans}:
            raise StateError("NVIDIA settings actual related fan roster changed.")
        selected = tuple(fan for fan in fans if fan.native_fan_id == int(suffix))
        if len(selected) != 1:
            raise StateError("NVIDIA settings actual fan relation is ambiguous.")
        attribute = selected[0].attribute
        minimum, maximum = attribute.minimum, attribute.maximum
        if minimum is None or maximum is None:
            raise StateError("NVIDIA settings actual fan range is unavailable.")
        policy = parse_settings_attribute(
            query_settings_output(session, f"[gpu:{native_id}]/GPUFanControlState"),
            attribute="GPUFanControlState",
            target_type="gpu",
            target_id=native_id,
        ).value
        if (
            not is_strict_int(policy)
            or policy not in (0, 1)
            or not is_strict_int(member.original_mode)
            or member.original_mode not in (0, 1)
        ):
            raise ValidationError("NVIDIA settings actual or original fan policy is invalid.")
        if goal == "requested" and (
            record.requested_units[member.field] != "%"
            or (record.requested_modes[member.field] == "auto") != (mode == 0)
            or (mode == 1 and record.requested_settings[member.field] != value)
        ):
            raise ValidationError("NVIDIA settings frozen fan target conflicts with user intent.")
        original_valid = (
            member.original_mode == 0
            and member.original_value is None
            or member.original_mode == 1
            and is_strict_int(member.original_value)
            and minimum <= member.original_value <= maximum
        )
        target_valid = (
            mode == 0
            and value is None
            or mode == 1
            and is_strict_int(value)
            and minimum <= value <= maximum
        )
        current_value = None if policy == 0 else attribute.value
        setup = (
            stage
            and policy != member.original_mode
            and any(
                item.backend == "nvidia_settings"
                and item.member_id == "gpu_fan_policy"
                and item.field in ("fan_control_policy", "fan_speed")
                and item.original_mode == member.original_mode
                and item.requested_mode == policy
                for item in record.members
            )
        )
        unchanged = (current_value, policy) == (
            member.original_value,
            member.original_mode,
        ) or setup
        matched = target_valid and (current_value, policy) == (value, mode)
        return SettingsMemberState(
            NativeMemberObservation(current_value, policy, matched),
            original_valid
            and target_valid
            and (not stage or mode == 0 or policy == 1)
            and (goal == "original" or unchanged),
            f"[fan:{int(suffix)}]/GPUTargetFanSpeed",
            (
                require_int_in_range_strict(
                    value,
                    minimum=minimum,
                    maximum=maximum,
                    error_message="NVIDIA settings frozen fan target is invalid.",
                )
                if mode == 1 and target_valid
                else None
            ),
        )
    clock_routes = {
        "core_clock": ("GPUGraphicsClockOffset", 0, "MHz"),
        "mem_clock": ("GPUMemoryTransferRateOffset", 2, "transfer_MHz"),
    }
    if (
        member.field not in clock_routes
        or (member.member_id, member.domain_id, member.native_unit) != clock_routes[member.field]
        or not is_strict_int(member.pstate_id)
        or member.original_mode is not None
        or mode is not None
    ):
        raise ValidationError("NVIDIA settings frozen clock relation is invalid.")
    if not is_strict_int(value):
        raise ValidationError("NVIDIA settings frozen native clock target is invalid.")
    if goal == "requested" and (
        record.requested_units[member.field] != "MHz"
        or record.requested_modes[member.field] not in ("auto", "manual")
        or (record.requested_modes[member.field] == "auto" and value != 0)
    ):
        raise ValidationError("NVIDIA settings frozen clock policy or user unit is invalid.")
    performances = query_settings_performance_modes(session, native_gpu_id=native_id)
    selected_performance = tuple(item for item in performances if item.level == member.pstate_id)
    if len(selected_performance) != 1:
        raise StateError("NVIDIA settings native performance relation changed.")
    performance = selected_performance[0]
    editable = (
        performance.graphics_editable
        if member.domain_id == 0
        else performance.memory_transfer_editable
    )
    if editable is False:
        raise StateError("NVIDIA settings native clock facility is no longer editable.")
    attribute_target = f"[gpu:{native_id}]/{member.member_id}[{member.pstate_id}]"
    observed = parse_settings_attribute(
        query_settings_output(session, attribute_target),
        attribute=member.member_id,
        target_type="gpu",
        target_id=native_id,
    )
    minimum, maximum = observed.minimum, observed.maximum
    if minimum is None or maximum is None:
        raise StateError("NVIDIA settings native clock range is unavailable.")
    restorable = (
        is_strict_int(member.original_value) and minimum <= member.original_value <= maximum
    )
    meaning = minimum <= value <= maximum
    if goal == "requested" and record.requested_modes[member.field] != "auto":
        meaning = (
            meaning
            and member.domain_id == 0
            and performance.graphics_maximum is not None
            and performance.graphics_maximum - observed.value
            == require_positive_int_strict(
                record.requested_settings[member.field],
                error_message="NVIDIA settings frozen graphics user target is invalid.",
            )
            - value
        )
    safe = (
        restorable and meaning and (goal == "original" or observed.value == member.original_value)
    )
    return SettingsMemberState(
        NativeMemberObservation(observed.value, None, observed.value == value and meaning),
        safe,
        attribute_target,
        value,
    )
