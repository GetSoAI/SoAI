"""SoAI - Fresh Intel configured native domains and physical command binding [backend/hardware/vendors/intel/native_control_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_control_types import NativeMemberObservation
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState, GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.serialization.json_parsing import MAX_JSON_NESTING_DEPTH, parse_json_value
from core.system.commands import require_command_result
from core.system.protocols import CommandExecutorProtocol
from core.types.json import JSONDict, JSONValue
from core.types.json_value import require_json_dict
from core.validation.strict_integer import is_strict_int
from core.validation.strict_numbers import require_non_negative_int_strict
from hardware.gpu_inventory.executable_resolution import (
    GpuExecutableResolution,
    GpuExecutableState,
    require_gpu_executable_selector,
)
from hardware.gpu_inventory.physical_binding import (
    match_gpu_physical_identity,
    resolve_gpu_physical_binding,
)
from hardware.gpu_tuning.control_recovery_records import recovery_member_key
from hardware.vendors.intel.physical_binding import acquire_intel_discovery_observations

__all__ = (
    "IntelFrequencyDomain",
    "IntelNativeControlState",
    "acquire_intel_control_state",
    "intel_frequency_footprint",
    "read_intel_frequency_pair",
)


@dataclass(frozen=True, slots=True)
class IntelFrequencyDomain:
    tile_id: int
    minimum: int
    maximum: int
    options: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class IntelNativeControlState:
    target: GPUPhysicalDevice
    native_device_id: int
    frequencies: tuple[IntelFrequencyDomain, ...]
    configured_power: tuple[tuple[str, int], ...]
    configured_power_range: JSONValue


def acquire_intel_control_state(
    executor: CommandExecutorProtocol,
    *,
    target: GPUPhysicalDevice,
    executable: GpuExecutableResolution,
    fields: tuple[str, ...],
) -> IntelNativeControlState:
    if (
        not isinstance(fields, tuple)
        or not fields
        or not set(fields).issubset(("power_limit", "core_clock"))
    ):
        raise ValidationError("Intel selected configured fields are invalid.")
    require_gpu_executable_selector(executable, executable="xpu-smi")
    if executable.state != GpuExecutableState.FOUND or executable.path is None:
        raise StateError("Intel configured query executable is unavailable.")
    roster = acquire_intel_discovery_observations(executor, executable=executable.path)
    candidates: list[JSONDict] = []
    for device in roster.devices:
        candidates.append(
            {
                "type": "intel",
                "uuid": device.identity.uuid if device.identity is not None else None,
                "pci_bdf_full": (
                    device.identity.pci_bdf_full if device.identity is not None else None
                ),
                "pci_bdf_observations": list(device.pci_bdf_observations),
            }
        )
    selected_facts: JSONDict = {
        "device_id": target.device_id,
        "type": target.vendor,
        "uuid": target.identity.uuid,
        "pci_bdf_full": target.identity.pci_bdf_full,
        "pci_bdf_observations": list(target.pci_bdf_observations),
    }
    binding = resolve_gpu_physical_binding(selected_facts, candidates)
    if binding.state != GPUPhysicalBindingState.BOUND or binding.device is None:
        raise StateError("Intel configured query physical relation is unavailable.")
    selected = tuple(
        device
        for device, candidate in zip(roster.devices, candidates, strict=True)
        if match_gpu_physical_identity(selected_facts, candidate) == GPUPhysicalBindingState.BOUND
    )
    if len(selected) != 1:
        raise StateError("Intel configured query has no unique actual native locator.")
    device = selected[0]
    if device.device_state is not None or device.recovery_action is not None:
        raise StateError("Intel configured device reports an unresolved recovery state.")
    result = executor.execute(
        [executable.path, "config", "-d", str(device.native_device_id), "-j"],
        timeout=5,
        shell=False,
        use_sudo=False,
    )
    require_command_result(result, error_message="Intel configured query response is invalid.")
    if result.return_code != 0:
        raise StateError(
            "Intel configured query failed before native effects.",
            details={
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.return_code,
                "actuator_invoked": False,
            },
        )
    try:
        payload = require_json_dict(
            parse_json_value(
                result.stdout,
                field="Intel configured domains",
                max_depth=MAX_JSON_NESTING_DEPTH,
                reject_duplicate_keys=True,
            ),
            label="Intel configured domains",
        )
        native_id = require_non_negative_int_strict(
            payload.get("device_id"), error_message="Intel configured device ID is invalid."
        )
        if native_id != device.native_device_id:
            raise StateError("Intel configured device ID contradicts its fresh physical locator.")
        frequencies = _frequency_domains(payload, native_id) if "core_clock" in fields else ()
        power: list[tuple[str, int]] = []
        for field in (
            (
                "pl_card_sustain",
                "pl_card_burst",
                "pl_card_peak",
                "pl_package_sustain",
                "pl_package_burst",
                "pl_package_peak",
            )
            if "power_limit" in fields
            else ()
        ):
            value = payload.get(field)
            if value is None or value == "N/A":
                continue
            if not is_strict_int(value) or value <= 0:
                raise ValidationError("Intel configured power original is invalid.")
            power.append((field, value))
    except (StateError, ValidationError) as exception:
        raise StateError(
            "Intel configured domain observations are invalid.",
            details={
                "stdout": result.stdout,
                "stderr": result.stderr,
                "actuator_invoked": False,
            },
            cause=exception,
        ) from exception
    return IntelNativeControlState(
        target, native_id, frequencies, tuple(power), payload.get("power_valid_range")
    )


def _frequency_domains(payload: JSONDict, native_id: int) -> tuple[IntelFrequencyDomain, ...]:
    rows = payload.get("tile_config_data")
    if rows is None:
        return ()
    if not isinstance(rows, list):
        raise ValidationError("Intel configured tile roster is invalid.")
    frequencies: list[IntelFrequencyDomain] = []
    tile_ids: set[int] = set()
    for item in rows:
        row = require_json_dict(item, label="Intel configured tile")
        locator = row.get("tile_id")
        if not isinstance(locator, str):
            raise ValidationError("Intel configured tile locator is unavailable.")
        match = re.fullmatch(r"(0|[1-9][0-9]*)/(0|[1-9][0-9]*)", locator)
        if match is None or int(match[1]) != native_id:
            raise ValidationError("Intel configured tile does not belong to its actual device.")
        tile = int(match[2])
        if tile in tile_ids:
            raise ValidationError("Intel configured tile is duplicated.")
        tile_ids.add(tile)
        options_text = row.get("gpu_frequency_valid_options")
        if not isinstance(options_text, str) or not re.fullmatch(
            r"[0-9]+(?:,[0-9]+)+", options_text
        ):
            raise ValidationError("Intel configured frequency options are invalid.")
        options = tuple(int(value) for value in options_text.split(","))
        if len(set(options)) != len(options) or any(value < 0 for value in options):
            raise ValidationError("Intel configured frequency options are duplicated or invalid.")
        minimum = require_non_negative_int_strict(
            row.get("min_frequency"), error_message="Intel configured minimum is invalid."
        )
        maximum = require_non_negative_int_strict(
            row.get("max_frequency"), error_message="Intel configured maximum is invalid."
        )
        if minimum not in options or maximum not in options or minimum > maximum:
            raise ValidationError("Intel configured range contradicts its actual options.")
        frequencies.append(IntelFrequencyDomain(tile, minimum, maximum, tuple(sorted(options))))
    return tuple(frequencies)


def intel_frequency_footprint(
    record: GPURecoveryRecord, member: GPURecoveryMember
) -> tuple[GPURecoveryMember, ...]:
    if (
        member.backend != "intel_xpum"
        or member.field != "core_clock"
        or not is_strict_int(member.domain_id)
    ):
        raise StateError("Intel selected member has no proved paired configured actuator.")
    members = tuple(
        member if recovery_member_key(item) == recovery_member_key(member) else item
        for item in record.members
        if item.backend == "intel_xpum"
        and item.field == "core_clock"
        and item.domain_id == member.domain_id
    )
    minimum = tuple(item for item in members if item.member_id == "frequency:min")
    maximum = tuple(item for item in members if item.member_id == "frequency:max")
    if len(members) != 2 or len(minimum) != 1 or len(maximum) != 1 or member not in members:
        raise ValidationError("Intel paired actuator requires both exact frozen endpoint members.")
    return minimum + maximum


def read_intel_frequency_pair(
    executor: CommandExecutorProtocol,
    executable: GpuExecutableResolution,
    record: GPURecoveryRecord,
    target: GPUPhysicalDevice,
    member: GPURecoveryMember,
    *,
    goal: Literal["requested", "original"],
) -> tuple[
    IntelNativeControlState,
    tuple[GPURecoveryMember, ...],
    tuple[NativeMemberObservation, ...],
    bool,
]:
    if goal not in ("requested", "original"):
        raise ValidationError("Intel configured invocation requires its explicit goal.")
    footprint = intel_frequency_footprint(record, member)
    state = acquire_intel_control_state(
        executor, target=target, executable=executable, fields=("core_clock",)
    )
    recorded_keys = {
        (item.domain_id, item.member_id)
        for item in record.members
        if item.backend == "intel_xpum" and item.field == "core_clock"
    }
    actual_keys = {
        (domain.tile_id, f"frequency:{endpoint}")
        for domain in state.frequencies
        for endpoint in ("min", "max")
    }
    if recorded_keys != actual_keys:
        raise StateError("Intel actual paired frequency-domain coverage changed.")
    domains = tuple(domain for domain in state.frequencies if domain.tile_id == member.domain_id)
    if len(domains) != 1:
        raise StateError("Intel actual selected frequency domain is unavailable.")
    domain = domains[0]
    values = tuple(
        item.original_value if goal == "original" else item.requested_value for item in footprint
    )
    if any(
        item.native_unit != "MHz"
        or item.pstate_id is not None
        or item.original_mode is not None
        or item.requested_mode is not None
        or not is_strict_int(item.original_value)
        for item in footprint
    ):
        raise ValidationError("Intel frozen endpoint native units or modes are invalid.")
    if any(not is_strict_int(value) or value not in domain.options for value in values):
        raise ValidationError("Intel frozen endpoint target is outside actual options.")
    minimum, maximum = values
    if not is_strict_int(minimum) or not is_strict_int(maximum):
        raise ValidationError("Intel frozen endpoint target must be a native integer.")
    if minimum > maximum:
        raise ValidationError("Intel frozen paired minimum exceeds its maximum.")
    meaning = all(item.original_value in domain.options for item in footprint)
    if goal == "requested":
        meaning = meaning and (
            record.requested_units[member.field] == "MHz"
            and record.requested_modes[member.field] == "manual"
            and values[0] == footprint[0].original_value
            and values[1] == record.requested_settings[member.field]
        )
    current = domain.minimum, domain.maximum
    observed = tuple(
        NativeMemberObservation(value, None, value == target and meaning)
        for value, target in zip(current, values, strict=True)
    )
    safe = meaning and (
        goal == "original" or current == tuple(item.original_value for item in footprint)
    )
    return state, footprint, observed, safe
