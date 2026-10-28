"""SoAI - Complete NVIDIA settings native originals and requested targets [backend/hardware/vendors/nvidia/settings_control_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.hardware.gpu_settings_contract import GPU_DIRECT_SETTING_FIELDS
from core.types.json import JSONDict
from core.validation.strict_numbers import (
    require_int_in_range_strict,
    require_non_negative_int_strict,
    require_positive_int_strict,
)
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_tuning.control_recovery_records import (
    create_observed_recovery_member,
    create_prepared_recovery_record,
)
from hardware.vendors.nvidia.settings_control_queries import (
    NvidiaSettingsSession,
    parse_settings_attribute,
    query_settings_fans,
    query_settings_output,
    query_settings_performance_modes,
)
from hardware.vendors.nvidia.settings_physical_binding import acquire_settings_physical_binding

__all__ = ("prepare_settings_control_record",)


def prepare_settings_control_record(
    session: NvidiaSettingsSession,
    *,
    target: GPUPhysicalDevice,
    operation_id: str,
    requested_settings: JSONDict,
    requested_modes: JSONDict,
) -> GPURecoveryRecord:
    require_canonical_trimmed_json_text(
        operation_id, error_message="NVIDIA settings operation identifier is invalid."
    )
    settings, modes = copy.deepcopy(requested_settings), copy.deepcopy(requested_modes)
    if (
        not settings
        or not set(settings).issubset(GPU_DIRECT_SETTING_FIELDS)
        or set(settings) != set(modes)
    ):
        raise ValidationError(
            "NVIDIA settings preparation requires complete user fields and modes."
        )
    for field, value in settings.items():
        if modes[field] not in ("auto", "manual") or (value == "auto" and modes[field] != "auto"):
            raise ValidationError("NVIDIA settings requested mode conflicts with the user value.")
        if value != "auto":
            if field == "fan_speed":
                require_non_negative_int_strict(
                    value, error_message="NVIDIA fan request is invalid."
                )
            else:
                require_positive_int_strict(
                    value, error_message="NVIDIA requested value is invalid."
                )
    if "power_limit" in settings:
        raise StateError("NVIDIA settings has no declared power-limit control facility.")
    bound = acquire_settings_physical_binding(session, target=target)
    members: list[GPURecoveryMember] = []
    units: JSONDict = {}
    if "fan_speed" in settings:
        members.extend(_prepare_fans(session, bound.native_gpu_id, settings, modes))
        units["fan_speed"] = "%"
        if "fan_control_policy" in settings:
            units["fan_control_policy"] = "policy"
    for field, attribute, domain in (
        ("core_clock", "GPUGraphicsClockOffset", 0),
        ("mem_clock", "GPUMemoryTransferRateOffset", 2),
    ):
        if field in settings:
            members.extend(
                _prepare_clocks(
                    session, bound.native_gpu_id, settings, modes, field, attribute, domain
                )
            )
            units[field] = "MHz"
    return create_prepared_recovery_record(
        operation_id=operation_id,
        backend="nvidia_settings",
        requested_settings=settings,
        requested_modes=modes,
        requested_units=units,
        members=tuple(members),
        target=bound.device,
    )


def _prepare_fans(
    session: NvidiaSettingsSession, native_id: int, settings: JSONDict, modes: JSONDict
) -> list[GPURecoveryMember]:
    policy = parse_settings_attribute(
        query_settings_output(session, f"[gpu:{native_id}]/GPUFanControlState"),
        attribute="GPUFanControlState",
        target_type="gpu",
        target_id=native_id,
    ).value
    policy = require_int_in_range_strict(
        policy, minimum=0, maximum=1, error_message="NVIDIA settings actual fan policy is invalid."
    )
    automatic = modes["fan_speed"] == "auto"
    requested_policy = 0 if automatic else 1
    policy_field = "fan_speed" if automatic else "fan_control_policy"
    members: list[GPURecoveryMember] = []
    if automatic or policy != requested_policy:
        members.append(
            create_observed_recovery_member(
                field=policy_field,
                member_id="gpu_fan_policy",
                original_value=None,
                original_mode=policy,
                requested_value=None,
                requested_mode=requested_policy,
                backend="nvidia_settings",
                native_unit="policy",
                domain_id=None,
                pstate_id=None,
            )
        )
        if not automatic:
            settings[policy_field], modes[policy_field] = 1, "manual"
    if automatic and policy == 0:
        return members
    for fan in query_settings_fans(session, native_gpu_id=native_id):
        minimum, maximum = fan.attribute.minimum, fan.attribute.maximum
        if minimum is None or maximum is None:
            raise StateError("NVIDIA settings fan target range is unavailable.")
        original = None
        if policy == 1:
            original = require_int_in_range_strict(
                fan.attribute.value,
                minimum=minimum,
                maximum=maximum,
                error_message="NVIDIA settings manual fan original cannot be restored.",
            )
        requested = (
            None
            if automatic
            else require_int_in_range_strict(
                settings["fan_speed"],
                minimum=minimum,
                maximum=maximum,
                error_message="NVIDIA settings fan target is outside the actual range.",
            )
        )
        members.append(
            create_observed_recovery_member(
                field="fan_speed",
                member_id=f"fan:{fan.native_fan_id}",
                original_value=original,
                original_mode=policy,
                requested_value=requested,
                requested_mode=requested_policy,
                backend="nvidia_settings",
                native_unit="%",
                domain_id=None,
                pstate_id=None,
            )
        )
    return members


def _prepare_clocks(
    session: NvidiaSettingsSession,
    native_id: int,
    settings: JSONDict,
    modes: JSONDict,
    field: str,
    attribute: str,
    domain: int,
) -> list[GPURecoveryMember]:
    performance_modes = query_settings_performance_modes(session, native_gpu_id=native_id)
    available = tuple(
        mode
        for mode in performance_modes
        if (mode.graphics_editable if domain == 0 else mode.memory_transfer_editable) is not False
    )
    if not available:
        raise StateError(
            "NVIDIA settings clock domain is not editable.",
            details={"reason": "unsupported", "field": field},
        )
    automatic = modes[field] == "auto"
    if not automatic and domain == 2:
        raise StateError(
            "NVIDIA memory transfer offset has no proved chip-frequency conversion.",
            details={"field": field, "reason": "conversion_unavailable"},
        )
    selected = available if automatic else (max(available, key=lambda mode: mode.level),)
    members: list[GPURecoveryMember] = []
    for performance in selected:
        observed = parse_settings_attribute(
            query_settings_output(session, f"[gpu:{native_id}]/{attribute}[{performance.level}]"),
            attribute=attribute,
            target_type="gpu",
            target_id=native_id,
        )
        minimum, maximum = observed.minimum, observed.maximum
        if minimum is None or maximum is None:
            raise StateError("NVIDIA settings clock range is unavailable.")
        original = require_int_in_range_strict(
            observed.value,
            minimum=minimum,
            maximum=maximum,
            error_message="NVIDIA settings native clock original cannot be restored.",
        )
        requested = 0
        if not automatic:
            if performance.graphics_maximum is None or performance.graphics_maximum <= 0:
                raise StateError("NVIDIA settings actual graphics conversion is unavailable.")
            requested = require_positive_int_strict(
                settings[field], error_message="NVIDIA graphics request is invalid."
            ) - (performance.graphics_maximum - original)
        requested = require_int_in_range_strict(
            requested,
            minimum=minimum,
            maximum=maximum,
            error_message="NVIDIA settings native clock target is outside the actual range.",
        )
        members.append(
            create_observed_recovery_member(
                field=field,
                member_id=attribute,
                original_value=original,
                original_mode=None,
                requested_value=requested,
                requested_mode=None,
                backend="nvidia_settings",
                native_unit="MHz" if domain == 0 else "transfer_MHz",
                domain_id=domain,
                pstate_id=performance.level,
            )
        )
    return members
