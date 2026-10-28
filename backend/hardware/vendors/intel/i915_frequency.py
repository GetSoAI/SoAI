"""SoAI - Physical i915 GT0 configured frequency authority [backend/hardware/vendors/intel/i915_frequency.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import open_text
from core.hardware.gpu_control_types import NativeMemberObservation
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.system.protocols import CommandExecutorProtocol
from core.types.json import JSONDict
from core.validation.strict_integer import is_strict_int
from hardware.gpu_inventory.drm_physical_observations import parse_drm_uevent
from hardware.gpu_inventory.sysfs_metrics import read_hwmon_scaled, read_sysfs_metric
from hardware.gpu_tuning.control_recovery_records import require_record_target
from hardware.vendors.intel.i915_tool_telemetry import read_i915_tool_telemetry

__all__ = (
    "I915FrequencyState",
    "i915_drm_directory",
    "acquire_i915_frequency_state",
    "acquire_i915_physical_card",
    "acquire_i915_frequency_roster",
    "read_i915_frequency_member",
    "read_i915_frequency_pair",
    "read_i915_telemetry",
)


@dataclass(frozen=True, slots=True)
class I915FrequencyState:
    card_directory: str
    device_directory: str
    gt_directory: str
    pci_bdf: str
    minimum_mhz: int
    maximum_mhz: int
    current_mhz: int
    upper_bound_mhz: int
    writable: bool


def i915_drm_directory() -> str:
    return "/sys/class/drm"


def acquire_i915_physical_card(pci_bdf: str) -> tuple[str, str, str]:
    canonical = normalize_observed_full_pci_bdf(pci_bdf)
    if not canonical:
        raise ValidationError("i915 frequency requires an actual canonical full PCI identity.")
    candidates: list[tuple[str, str, str]] = []
    directory = i915_drm_directory()
    for name in sorted(os.listdir(directory)):
        if re.fullmatch(r"card[0-9]+", name) is None:
            continue
        card_directory = os.path.join(directory, name)
        device_directory = os.path.join(card_directory, "device")
        try:
            with open_text(os.path.join(device_directory, "uevent"), encoding="utf-8") as handle:
                rows = handle.read().splitlines()
        except FileNotFoundError:
            continue
        fields = parse_drm_uevent("\n".join(rows))
        observed_pci = fields.get("PCI_SLOT_NAME", "")
        if normalize_observed_full_pci_bdf(observed_pci) != canonical:
            continue
        if (
            fields.get("DRIVER") != "i915"
            or fields.get("PCI_ID", "").split(":")[0].casefold() != "8086"
            or os.path.basename(os.path.realpath(os.path.join(device_directory, "driver")))
            != "i915"
        ):
            raise StateError("The selected physical GPU is not bound to the i915 driver.")
        candidates.append((card_directory, device_directory, observed_pci))
    if len(candidates) != 1:
        raise StateError(
            "The selected physical i915 card relationship is unavailable or ambiguous."
        )
    return candidates[0]


def acquire_i915_frequency_state(pci_bdf: str) -> I915FrequencyState:
    card_directory, device_directory, observed_pci = acquire_i915_physical_card(pci_bdf)
    gt_parent = os.path.join(card_directory, "gt")
    if tuple(sorted(os.listdir(gt_parent))) != ("gt0",):
        raise StateError("The selected i915 frequency control requires its actual single GT0.")
    gt_directory = os.path.join(gt_parent, "gt0")
    minimum = _read_frequency(gt_directory, "rps_min_freq_mhz")
    maximum = _read_frequency(gt_directory, "rps_max_freq_mhz")
    current = _read_frequency(gt_directory, "rps_cur_freq_mhz")
    upper = _read_frequency(gt_directory, "rps_RP0_freq_mhz")
    if not minimum <= maximum <= upper:
        raise ValidationError("The actual i915 configured range exceeds its native upper bound.")
    return I915FrequencyState(
        card_directory,
        device_directory,
        gt_directory,
        observed_pci,
        minimum,
        maximum,
        current,
        upper,
        os.access(os.path.join(gt_directory, "rps_max_freq_mhz"), os.W_OK),
    )


def acquire_i915_frequency_roster() -> tuple[I915FrequencyState, ...]:
    directory = i915_drm_directory()
    states: list[I915FrequencyState] = []
    identities: set[str] = set()
    for name in sorted(os.listdir(directory)):
        if re.fullmatch(r"card[0-9]+", name) is None:
            continue
        path = os.path.join(directory, name, "device", "uevent")
        with open_text(path, encoding="utf-8") as handle:
            fields = parse_drm_uevent(handle.read())
        if fields.get("DRIVER") != "i915":
            continue
        pci = fields.get("PCI_SLOT_NAME", "")
        canonical = normalize_observed_full_pci_bdf(pci)
        if not canonical or canonical in identities:
            raise ValidationError("The actual i915 roster has unresolved physical identity.")
        identities.add(canonical)
        states.append(acquire_i915_frequency_state(pci))
    return tuple(states)


def _read_frequency(directory: str, filename: str) -> int:
    path = os.path.join(directory, filename)
    if not os.access(path, os.R_OK):
        raise PermissionError("The selected i915 frequency observation is unreadable.")
    with open_text(path, encoding="utf-8") as handle:
        value = handle.read().strip()
    if re.fullmatch(r"[0-9]+", value) is None or int(value) <= 0:
        raise ValidationError("The actual i915 frequency observation is invalid.")
    return int(value)


def read_i915_frequency_member(
    record: GPURecoveryRecord,
    target: GPUPhysicalDevice,
    member: GPURecoveryMember,
    *,
    goal: Literal["requested", "original"],
) -> tuple[I915FrequencyState, NativeMemberObservation]:
    require_record_target(record, target)
    if (
        target.vendor != "intel"
        or target.identity.pci_bdf_full is None
        or member not in record.members
        or goal not in ("requested", "original")
    ):
        raise ValidationError("i915 configured readback requires its physical target and goal.")
    if (
        (
            member.backend,
            member.field,
            member.domain_id,
            member.pstate_id,
            member.native_unit,
            member.original_mode,
            member.requested_mode,
        )
        != ("intel_i915", "core_clock", 0, None, "MHz", None, None)
        or not is_strict_int(member.domain_id)
        or member.member_id not in ("frequency:min", "frequency:max")
    ):
        raise ValidationError("i915 configured readback requires its exact physical GT0 member.")
    desired = member.original_value if goal == "original" else member.requested_value
    if not is_strict_int(desired) or desired <= 0:
        raise ValidationError("i915 configured goal requires a positive native MHz integer.")
    state = acquire_i915_frequency_state(target.identity.pci_bdf_full)
    value = state.minimum_mhz if member.member_id == "frequency:min" else state.maximum_mhz
    return state, NativeMemberObservation(value, None, value == desired)


def read_i915_frequency_pair(
    record: GPURecoveryRecord,
    target: GPUPhysicalDevice,
    member: GPURecoveryMember,
    *,
    goal: Literal["requested", "original"],
) -> tuple[I915FrequencyState, tuple[GPURecoveryMember, ...], tuple[NativeMemberObservation, ...]]:
    state, _ = read_i915_frequency_member(record, target, member, goal=goal)
    members = tuple(
        item
        for endpoint in ("frequency:min", "frequency:max")
        for item in record.members
        if item.backend == "intel_i915" and item.member_id == endpoint
    )
    if len(members) != 2 or member not in members:
        raise ValidationError(
            "i915 frequency requires its complete min-preservation/max footprint."
        )
    observations: list[NativeMemberObservation] = []
    for item, value in zip(members, (state.minimum_mhz, state.maximum_mhz), strict=True):
        desired = item.original_value if goal == "original" else item.requested_value
        if (
            item.field,
            item.domain_id,
            item.pstate_id,
            item.native_unit,
            item.original_mode,
            item.requested_mode,
        ) != ("core_clock", 0, None, "MHz", None, None) or not is_strict_int(item.domain_id):
            raise ValidationError("i915 frozen frequency footprint contains an invalid endpoint.")
        if not is_strict_int(desired) or desired <= 0:
            raise ValidationError("i915 frozen frequency footprint has an invalid native goal.")
        if item.member_id == "frequency:min" and item.requested_value != item.original_value:
            raise ValidationError("i915 minimum is a read-only preserved native obligation.")
        observations.append(NativeMemberObservation(value, None, value == desired))
    return state, members, tuple(observations)


def read_i915_telemetry(pci_bdf: str, executor: CommandExecutorProtocol) -> JSONDict:
    card_directory, device_directory, observed_pci = acquire_i915_physical_card(pci_bdf)
    metrics: JSONDict = {"memory_type": "shared"}
    fields = (
        ("gt_act_freq_mhz", "rps_act_freq_mhz", "core_clock_mhz"),
        ("gt_cur_freq_mhz", "rps_cur_freq_mhz", "requested_core_clock_mhz"),
        ("gt_min_freq_mhz", "rps_min_freq_mhz", "configured_minimum_core_clock_mhz"),
        ("gt_max_freq_mhz", "rps_max_freq_mhz", "configured_maximum_core_clock_mhz"),
    )
    for legacy_name, gt_name, field in fields:
        value = read_sysfs_metric(os.path.join(card_directory, legacy_name))
        if value is None:
            value = read_sysfs_metric(os.path.join(card_directory, "gt", "gt0", gt_name))
        if value is not None and value >= 0:
            metrics[field] = value
    metrics["temperature"] = read_hwmon_scaled(device_directory, "temp1_input", divisor=1000.0)
    try:
        metrics.update(read_i915_tool_telemetry(os.path.realpath(device_directory), executor))
    except (OSError, StateError, ValidationError) as exception:
        metrics["legacy_tool_unavailable_reason"] = (
            "permission_denied"
            if isinstance(exception, PermissionError)
            else "native_sensor_query_failed"
        )
    if acquire_i915_physical_card(pci_bdf) != (card_directory, device_directory, observed_pci):
        raise StateError("i915 physical relation changed during sensor acquisition.")
    return metrics
