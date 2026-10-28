"""SoAI - Intel configured native endpoint preparation without inferred defaults [backend/hardware/vendors/intel/control_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import replace

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.system.protocols import CommandExecutorProtocol
from core.types.json import JSONDict
from core.validation.strict_numbers import require_positive_int_strict
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_inventory.executable_resolution import GpuExecutableResolution
from hardware.gpu_tuning.control_recovery_records import (
    create_observed_recovery_member,
    create_prepared_recovery_record,
)
from hardware.vendors.intel.i915_frequency import acquire_i915_frequency_state
from hardware.vendors.intel.native_control_observations import acquire_intel_control_state

__all__ = (
    "prepare_i915_control_record",
    "prepare_intel_control_record",
)


def prepare_i915_control_record(
    *,
    target: GPUPhysicalDevice,
    operation_id: str,
    requested_settings: JSONDict,
    requested_modes: JSONDict,
) -> GPURecoveryRecord:
    require_canonical_trimmed_json_text(operation_id, error_message="i915 operation ID is invalid.")
    if (
        target.vendor != "intel"
        or target.identity.pci_bdf_full is None
        or set(requested_settings) != {"core_clock"}
        or requested_modes != {"core_clock": "manual"}
    ):
        raise StateError("i915 supports only physically scoped manual maximum frequency.")
    requested = require_positive_int_strict(
        requested_settings["core_clock"], error_message="i915 requested frequency is invalid."
    )
    state = acquire_i915_frequency_state(target.identity.pci_bdf_full)
    if not state.writable:
        raise PermissionError("The selected i915 maximum frequency is not writable.")
    if not state.minimum_mhz <= requested <= state.upper_bound_mhz:
        raise ValidationError("i915 requested maximum conflicts with actual native bounds.")
    member = create_observed_recovery_member(
        field="core_clock",
        member_id="frequency:max",
        domain_id=0,
        pstate_id=None,
        original_value=state.maximum_mhz,
        original_mode=None,
        native_unit="MHz",
        backend="intel_i915",
        requested_value=requested,
        requested_mode=None,
    )
    return create_prepared_recovery_record(
        operation_id=operation_id,
        backend="intel_i915",
        requested_settings=copy.deepcopy(requested_settings),
        requested_modes=copy.deepcopy(requested_modes),
        requested_units={"core_clock": "MHz"},
        members=(
            replace(
                member,
                member_id="frequency:min",
                original_value=state.minimum_mhz,
                requested_value=state.minimum_mhz,
            ),
            member,
        ),
        target=target,
    )


def prepare_intel_control_record(
    executor: CommandExecutorProtocol,
    *,
    executable: GpuExecutableResolution,
    target: GPUPhysicalDevice,
    operation_id: str,
    requested_settings: JSONDict,
    requested_modes: JSONDict,
) -> GPURecoveryRecord:
    require_canonical_trimmed_json_text(
        operation_id, error_message="Intel operation ID is invalid."
    )
    settings, modes = copy.deepcopy(requested_settings), copy.deepcopy(requested_modes)
    if (
        not settings
        or set(settings) != set(modes)
        or not set(settings).issubset(("power_limit", "fan_speed", "core_clock", "mem_clock"))
    ):
        raise ValidationError("Intel preparation requires complete selected user fields and modes.")
    for field, value in settings.items():
        if modes[field] not in ("auto", "manual") or (value == "auto" and modes[field] != "auto"):
            raise ValidationError("Intel user setting and requested policy conflict.")
        if value != "auto":
            require_positive_int_strict(value, error_message="Intel numeric request is invalid.")
    if "fan_speed" in settings or "mem_clock" in settings:
        raise StateError(
            "Intel selected backend has no configured fan or memory actuator.",
            details={"reason": "unsupported"},
        )
    state = acquire_intel_control_state(
        executor, target=target, executable=executable, fields=tuple(settings)
    )
    if "power_limit" in settings:
        raise StateError(
            "Intel selected power-domain command and constraint relation is unavailable."
        )
    if modes["core_clock"] == "auto":
        raise StateError("Intel actual automatic frequency policy is unavailable before effects.")
    requested = require_positive_int_strict(
        settings["core_clock"], error_message="Intel frequency request is invalid."
    )
    if not state.frequencies:
        raise StateError("Intel actual configured frequency-domain roster is unavailable.")
    members: list[GPURecoveryMember] = []
    for frequency in state.frequencies:
        if requested not in frequency.options or requested < frequency.minimum:
            raise ValidationError(
                "Intel requested frequency conflicts with actual configured options."
            )
        for endpoint, original, native_target in (
            ("min", frequency.minimum, frequency.minimum),
            ("max", frequency.maximum, requested),
        ):
            members.append(
                create_observed_recovery_member(
                    field="core_clock",
                    member_id=f"frequency:{endpoint}",
                    domain_id=frequency.tile_id,
                    pstate_id=None,
                    original_value=original,
                    original_mode=None,
                    native_unit="MHz",
                    backend="intel_xpum",
                    requested_value=native_target,
                    requested_mode=None,
                )
            )
    return create_prepared_recovery_record(
        operation_id=operation_id,
        backend="intel_xpum",
        requested_settings=settings,
        requested_modes=modes,
        requested_units={"core_clock": "MHz"},
        members=tuple(members),
        target=target,
    )
