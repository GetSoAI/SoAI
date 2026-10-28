"""SoAI - AMD native member originals, domains and conversion observations [backend/hardware/vendors/amd/control_member_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_control_types import NativeMemberObservation
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.system.protocols import CommandExecutorProtocol
from core.validation.strict_integer import is_strict_int
from hardware.vendors.amd.native_control_observations import acquire_amd_control_state

__all__ = (
    "AmdMemberState",
    "read_amd_member_state",
)


@dataclass(frozen=True, slots=True)
class AmdMemberState:
    observation: NativeMemberObservation
    safe: bool
    commands: tuple[tuple[str, str], ...]


def read_amd_member_state(
    executor: CommandExecutorProtocol,
    record: GPURecoveryRecord,
    target: GPUPhysicalDevice,
    member: GPURecoveryMember,
    *,
    goal: Literal["requested", "original"],
    stage: bool,
) -> AmdMemberState:
    if member.backend not in ("amd_smi", "amd_overdrive") or goal not in ("requested", "original"):
        raise ValidationError("AMD member requires its explicit native backend and goal.")
    state = acquire_amd_control_state(
        executor, target=target, fields=tuple(record.requested_settings)
    )
    value, mode = (
        (member.original_value, member.original_mode)
        if goal == "original"
        else (member.requested_value, member.requested_mode)
    )
    if member.field == "power_limit":
        selected = tuple(
            power for power in state.power_domains if member.member_id == f"power:{power.native_id}"
        )
        expected = {
            item.member_id
            for item in record.members
            if item.backend == member.backend and item.field == "power_limit"
        }
        if (
            expected != {f"power:{power.native_id}" for power in state.power_domains}
            or len(selected) != 1
        ):
            raise StateError("AMD actual power domain coverage changed.")
        power = selected[0]
        if (member.native_unit, member.domain_id, member.pstate_id, mode) != (
            "uW",
            None,
            None,
            None,
        ) or not is_strict_int(value):
            raise ValidationError("AMD power member native relation is invalid.")
        original_valid = (
            is_strict_int(member.original_value)
            and power.minimum <= member.original_value <= power.maximum
        )
        meaning = power.minimum <= value <= power.maximum
        if goal == "requested":
            requested = record.requested_settings[member.field]
            meaning = (
                meaning
                and isinstance(requested, int | float)
                and not isinstance(requested, bool)
                and requested * 1000000 == value
                and record.requested_units[member.field] == "W"
            )
            if record.requested_modes[member.field] == "auto":
                meaning = meaning and power.default == value
        return AmdMemberState(
            NativeMemberObservation(power.current, None, power.current == value and meaning),
            original_valid
            and meaning
            and (goal == "original" or power.current == member.original_value),
            ((power.path, str(value)),),
        )
    if member.field == "fan_speed":
        selected_fans = tuple(
            fan for fan in state.fans if member.member_id == f"fan:{fan.native_id}"
        )
        expected_fans = {
            item.member_id
            for item in record.members
            if item.backend == member.backend and item.field == "fan_speed"
        }
        if (
            expected_fans != {f"fan:{fan.native_id}" for fan in state.fans}
            or len(selected_fans) != 1
        ):
            raise StateError("AMD actual fan-policy coverage changed.")
        fan = selected_fans[0]
        if (
            (member.native_unit, member.domain_id, member.pstate_id) != ("PWM255", None, None)
            or not is_strict_int(mode)
            or mode not in (0, 1, 2)
        ):
            raise ValidationError("AMD frozen fan policy is invalid.")
        valid = (mode != 1 and value is None) or (
            mode == 1 and is_strict_int(value) and fan.minimum <= value <= fan.maximum
        )
        original_valid = (
            is_strict_int(member.original_mode)
            and member.original_mode in (0, 2)
            and member.original_value is None
        )
        if goal == "requested":
            valid = (
                valid
                and mode == 2
                and record.requested_modes[member.field] == "auto"
                and record.requested_units[member.field] == "%"
            )
        commands: tuple[tuple[str, str], ...] = ((fan.policy_path, str(mode)),)
        if mode == 1:
            commands += ((fan.path, str(value)),)
        observed = NativeMemberObservation(
            fan.observed_pwm, fan.policy, mode in (0, 2) and value is None and fan.policy == mode
        )
        return AmdMemberState(
            observed,
            original_valid
            and valid
            and (
                goal == "original"
                or (fan.observed_pwm, fan.policy) == (member.original_value, member.original_mode)
            ),
            commands,
        )
    if member.field == "performance_mode":
        if (
            (member.member_id, member.native_unit, member.domain_id, member.pstate_id, value)
            != ("performance", "policy", None, None, None)
            or not isinstance(mode, str)
            or mode
            not in (
                "auto",
                "manual",
                "low",
                "high",
                "profile_standard",
                "profile_min_sclk",
                "profile_min_mclk",
                "profile_peak",
            )
        ):
            raise ValidationError("AMD frozen performance policy is invalid.")
        if state.performance_mode is None:
            raise StateError("AMD actual performance original is unavailable.")
        return AmdMemberState(
            NativeMemberObservation(None, state.performance_mode, state.performance_mode == mode),
            goal == "original" or state.performance_mode == member.original_mode,
            ((state.performance_path, mode),),
        )
    if (
        member.field not in ("core_clock", "mem_clock")
        or member.backend != "amd_overdrive"
        or state.overdrive is None
    ):
        raise StateError("AMD member has no proved configured clock facility.")
    table = state.overdrive
    if table.additional_rows:
        raise StateError("AMD actual commit footprint includes unproved mutable domains.")
    native_levels = {
        (field, domain, f"clock:{index}"): clock
        for field, domain, levels in (
            ("core_clock", 0, table.sclk_levels),
            ("mem_clock", 1, table.mclk_levels),
        )
        for index, clock in levels
    }
    recorded_levels = {
        (item.field, item.domain_id, item.member_id)
        for item in record.members
        if item.backend == "amd_overdrive" and item.field in ("core_clock", "mem_clock")
    }
    if not is_strict_int(member.domain_id) or member.domain_id not in (0, 1):
        raise ValidationError("AMD clock native domain is invalid.")
    key = (member.field, member.domain_id, member.member_id)
    if set(native_levels) != recorded_levels or key not in native_levels:
        raise StateError("AMD native commit domain coverage changed.")
    ranges = {name: (minimum, maximum) for name, minimum, maximum in table.ranges}
    range_name = "SCLK" if member.domain_id == 0 else "MCLK"
    if (
        range_name not in ranges
        or not is_strict_int(value)
        or member.native_unit != "MHz"
        or mode is not None
    ):
        raise ValidationError("AMD clock native target or constraints are invalid.")
    minimum, maximum = ranges[range_name]
    valid = (
        minimum <= value <= maximum
        and is_strict_int(member.original_value)
        and minimum <= member.original_value <= maximum
    )
    current = native_levels[key]
    configured = state.performance_mode == "manual" or current == value
    if not stage and not configured:
        configured = any(
            item.backend == "amd_overdrive"
            and item.field == "performance_mode"
            and item.original_mode == state.performance_mode
            and item.requested_mode == "manual"
            for item in record.members
        )
    index = member.member_id.removeprefix("clock:")
    payload = f"{'s' if member.domain_id == 0 else 'm'} {index} {value}"
    return AmdMemberState(
        NativeMemberObservation(current, None, current == value and valid and configured),
        valid and configured and (goal == "original" or current == member.original_value),
        ((table.path, payload), (table.path, "c")),
    )
