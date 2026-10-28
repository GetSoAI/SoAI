"""SoAI - Complete AMD native original and target planning [backend/hardware/vendors/amd/control_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.hardware.gpu_settings_contract import GPU_DIRECT_SETTING_FIELDS
from core.system.protocols import CommandExecutorProtocol
from core.types.json import JSONDict
from core.validation.strict_numbers import require_int_in_range_strict, require_positive_int_strict
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_tuning.control_recovery_records import (
    create_observed_recovery_member,
    create_prepared_recovery_record,
)
from hardware.vendors.amd.native_control_observations import acquire_amd_control_state

__all__ = ("prepare_amd_control_record",)


def prepare_amd_control_record(
    executor: CommandExecutorProtocol,
    *,
    target: GPUPhysicalDevice,
    operation_id: str,
    control_backend: str,
    requested_settings: JSONDict,
    requested_modes: JSONDict,
) -> GPURecoveryRecord:
    require_canonical_trimmed_json_text(operation_id, error_message="AMD operation ID is invalid.")
    settings, modes = copy.deepcopy(requested_settings), copy.deepcopy(requested_modes)
    if (
        control_backend not in ("amd_smi", "amd_overdrive")
        or not settings
        or not set(settings).issubset(GPU_DIRECT_SETTING_FIELDS)
        or set(settings) != set(modes)
    ):
        raise ValidationError("AMD preparation requires complete selected user fields and modes.")
    for field, value in settings.items():
        if modes[field] not in ("auto", "manual") or (value == "auto" and modes[field] != "auto"):
            raise ValidationError("AMD requested policy conflicts with its user value.")
        if value != "auto":
            if field == "fan_speed":
                require_int_in_range_strict(
                    value, minimum=0, maximum=100, error_message="AMD fan percent is invalid."
                )
            else:
                require_positive_int_strict(value, error_message="AMD numeric target is invalid.")
    state = acquire_amd_control_state(executor, target=target, fields=tuple(settings))
    members: list[GPURecoveryMember] = []
    units: JSONDict = {}
    if "power_limit" in settings:
        if not state.power_domains:
            raise StateError("AMD actual power-cap facility is unavailable.")
        automatic: set[int] = set()
        for power in state.power_domains:
            native = (
                power.default
                if modes["power_limit"] == "auto"
                else require_positive_int_strict(
                    settings["power_limit"], error_message="AMD watts are invalid."
                )
                * 1000000
            )
            if native is None:
                raise StateError("AMD automatic power target is unavailable.")
            native = require_int_in_range_strict(
                native,
                minimum=power.minimum,
                maximum=power.maximum,
                error_message="AMD power target is outside actual constraints.",
            )
            if not power.minimum <= power.current <= power.maximum:
                raise ValidationError("AMD original power cap cannot be restored.")
            automatic.add(native)
            members.append(
                create_observed_recovery_member(
                    field="power_limit",
                    member_id=f"power:{power.native_id}",
                    original_value=power.current,
                    original_mode=None,
                    requested_value=native,
                    requested_mode=None,
                    backend=control_backend,
                    native_unit="uW",
                    domain_id=None,
                    pstate_id=None,
                )
            )
        if modes["power_limit"] == "auto":
            if len(automatic) != 1:
                raise StateError("AMD automatic power domains have no uniform user-watt target.")
            settings["power_limit"] = next(iter(automatic)) / 1000000
        units["power_limit"] = "W"
    if "fan_speed" in settings:
        if not state.fans:
            raise StateError("AMD actual fan-policy facility is unavailable.")
        if modes["fan_speed"] != "auto":
            raise StateError("AMD selected fan percent readback conversion is unproved.")
        for fan in state.fans:
            if fan.policy == 1:
                raise StateError("AMD manual fan original configured target is unproved.")
            members.append(
                create_observed_recovery_member(
                    field="fan_speed",
                    member_id=f"fan:{fan.native_id}",
                    original_value=fan.observed_pwm,
                    original_mode=fan.policy,
                    requested_value=None,
                    requested_mode=2,
                    backend=control_backend,
                    native_unit="PWM255",
                    domain_id=None,
                    pstate_id=None,
                )
            )
        settings["fan_speed"] = "auto"
        units["fan_speed"] = "%"
    if "core_clock" in settings or "mem_clock" in settings:
        if control_backend != "amd_overdrive" or state.overdrive is None:
            raise StateError("AMD configured native clock-domain authority is unavailable.")
        if state.overdrive.additional_rows:
            raise StateError("AMD native commit footprint includes unproved mutable domains.")
        if any(
            modes[field] == "auto" for field in ("core_clock", "mem_clock") if field in settings
        ):
            raise StateError("AMD native clock reset defaults are not observable before effects.")
        if "mem_clock" in settings:
            raise StateError("AMD memory-controller MHz to public memory units is unproved.")
        ranges = {name: (minimum, maximum) for name, minimum, maximum in state.overdrive.ranges}
        if "SCLK" not in ranges or not any(index == 1 for index, _ in state.overdrive.sclk_levels):
            raise StateError("AMD configured graphics maximum and range are unavailable.")
        requested = require_int_in_range_strict(
            settings["core_clock"],
            minimum=ranges["SCLK"][0],
            maximum=ranges["SCLK"][1],
            error_message="AMD graphics target is outside actual constraints.",
        )
        for field, domain, levels in (
            ("core_clock", 0, state.overdrive.sclk_levels),
            ("mem_clock", 1, state.overdrive.mclk_levels),
        ):
            for index, original in levels:
                native = requested if domain == 0 and index == 1 else original
                members.append(
                    create_observed_recovery_member(
                        field=field,
                        member_id=f"clock:{index}",
                        original_value=original,
                        original_mode=None,
                        requested_value=native,
                        requested_mode=None,
                        backend=control_backend,
                        native_unit="MHz",
                        domain_id=domain,
                        pstate_id=None,
                    )
                )
            if levels:
                if field not in settings:
                    settings[field], modes[field] = max(value for _, value in levels), "manual"
                units[field] = "MHz"
        if any(
            member.original_value != member.requested_value
            for member in members
            if member.field == "core_clock"
        ):
            if state.performance_mode is None:
                raise StateError("AMD clock commit requires its actual performance original.")
            members.insert(
                0,
                create_observed_recovery_member(
                    field="performance_mode",
                    member_id="performance",
                    original_value=None,
                    original_mode=state.performance_mode,
                    requested_value=None,
                    requested_mode="manual",
                    backend=control_backend,
                    native_unit="policy",
                    domain_id=None,
                    pstate_id=None,
                ),
            )
            settings["performance_mode"], modes["performance_mode"], units["performance_mode"] = (
                "manual",
                "manual",
                "policy",
            )
    return create_prepared_recovery_record(
        operation_id=operation_id,
        backend=control_backend,
        requested_settings=settings,
        requested_modes=modes,
        requested_units=units,
        members=tuple(members),
        target=state.bound.device,
    )
