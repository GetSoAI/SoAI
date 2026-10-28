"""SoAI - Fresh AMD native physical binding [backend/hardware/vendors/amd/physical_binding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingState,
    GPUPhysicalDevice,
    GPUPhysicalIdentity,
)
from core.hardware.gpu_physical_observations import read_gpu_physical_identity
from core.types.json_value import require_json_dict
from core.validation.strict_integer import is_strict_int
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_inventory.physical_binding import (
    match_gpu_physical_identity,
    resolve_gpu_physical_binding,
)
from hardware.vendors.command_probe import JsonCommandProbeState, run_json_command_probe

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue


__all__ = (
    "AmdBoundDevice",
    "AmdObservedDevice",
    "acquire_amd_physical_roster",
    "acquire_amd_physical_binding",
    "project_amd_smi_physical_observations",
)


@dataclass(frozen=True, slots=True)
class AmdBoundDevice:
    device: GPUPhysicalDevice
    native_device_id: int


@dataclass(frozen=True, slots=True)
class AmdObservedDevice:
    native_device_id: int
    identity: GPUPhysicalIdentity
    pci_bdf_observations: tuple[str, ...]


def acquire_amd_physical_roster(executor: CommandExecutorProtocol) -> tuple[AmdObservedDevice, ...]:
    result = run_json_command_probe(
        executor,
        ["amd-smi", "static", "-g", "all", "-a", "-b", "-d", "-v", "-l", "--json"],
        timeout=10,
        use_sudo=False,
        json_field="AMD native identity roster",
        framing="amd_smi",
    )
    if result.state == JsonCommandProbeState.MALFORMED:
        raise ValidationError(
            "AMD native identity output is malformed.",
            details=result.private_details,
            cause=result.failure,
        )
    if result.state != JsonCommandProbeState.OBSERVED or result.payload is None:
        raise StateError(
            "AMD native identity query failed.",
            details=result.private_details,
            cause=result.failure,
        )
    payload = result.payload
    candidates: list[JSONDict] = []
    observations: list[AmdObservedDevice] = []
    native_ids: set[int] = set()
    for native_id, entry in _native_rows(payload):
        if native_id in native_ids:
            raise StateError("AMD native identity roster contains duplicate native locators.")
        native_ids.add(native_id)
        candidate = project_amd_smi_physical_observations(entry)
        candidate["vendor_id"] = native_id
        identity = read_gpu_physical_identity(candidate)
        if identity is None:
            raise ValidationError("AMD native identity roster contains an unidentifiable device.")
        if any(
            match_gpu_physical_identity(candidate, previous)
            in (GPUPhysicalBindingState.BOUND, GPUPhysicalBindingState.IDENTITY_CONFLICT)
            for previous in candidates
        ):
            raise StateError(
                "AMD native identity roster contains duplicate or conflicting devices."
            )
        candidates.append(candidate)
        pci = candidate["pci_bdf_observations"]
        if not isinstance(pci, list) or any(not isinstance(value, str) for value in pci):
            raise ValidationError("AMD actual PCI observations are invalid.")
        observations.append(
            AmdObservedDevice(
                native_id, identity, tuple(value for value in pci if isinstance(value, str))
            )
        )
    return tuple(observations)


def acquire_amd_physical_binding(
    executor: CommandExecutorProtocol, *, target: GPUPhysicalDevice
) -> AmdBoundDevice:
    if target.vendor.casefold() != "amd":
        raise ValidationError("AMD native binding requires an AMD physical target.")
    roster = acquire_amd_physical_roster(executor)
    candidates: list[JSONDict] = [
        {
            "type": "amd",
            "uuid": row.identity.uuid,
            "pci_bdf_observations": list(row.pci_bdf_observations),
            "vendor_id": row.native_device_id,
        }
        for row in roster
    ]
    selected: JSONDict = {
        "device_id": target.device_id,
        "type": target.vendor,
        "uuid": target.identity.uuid,
        "pci_bdf_full": target.identity.pci_bdf_full,
        "pci_bdf_observations": list(target.pci_bdf_observations),
    }
    binding = resolve_gpu_physical_binding(selected, candidates)
    device = binding.device
    if binding.state != GPUPhysicalBindingState.BOUND or device is None:
        raise StateError(
            "AMD native physical target could not be bound.",
            details={"binding_state": binding.state.value, "reason": binding.reason_code},
        )
    if device.vendor_index is None:
        raise ValidationError("AMD native binding has no proved locator.")
    return AmdBoundDevice(device, device.vendor_index)


def _native_rows(payload: JSONValue) -> list[tuple[int, JSONDict]]:
    rows: list[tuple[int, JSONDict]] = []
    if isinstance(payload, dict):
        observed_root = _casefold_fields(payload)
        if set(observed_root) == {"gpu_data"}:
            payload = observed_root["gpu_data"]
    if isinstance(payload, list):
        for value in payload:
            entry = _casefold_fields(require_json_dict(value, label="AMD native device"))
            native_id = _native_identifier(entry.get("gpu"))
            rows.append((native_id, entry))
        return rows
    root = _casefold_fields(require_json_dict(payload, label="AMD native roster"))
    if set(root) != {"gpu"}:
        raise ValidationError("AMD native identity roster container is unsupported.")
    devices = require_json_dict(root["gpu"], label="AMD native device map")
    for key, value in devices.items():
        if not key.isascii() or not key.isdigit() or str(int(key)) != key:
            raise ValidationError("AMD native device map locator is invalid.")
        native_id = int(key)
        entry = _casefold_fields(require_json_dict(value, label="AMD native device"))
        if "gpu" in entry and _native_identifier(entry["gpu"]) != native_id:
            raise ValidationError("AMD native device locator observations conflict.")
        rows.append((native_id, entry))
    return rows


def _native_identifier(value: JSONValue) -> int:
    if not is_strict_int(value) or value < 0:
        raise ValidationError("AMD native device identifier is invalid.")
    return value


def _casefold_fields(entry: JSONDict) -> JSONDict:
    result: JSONDict = {}
    for key, value in entry.items():
        normalized = key.casefold()
        if normalized in result:
            raise ValidationError("AMD native field names conflict.")
        result[normalized] = value
    return result


def project_amd_smi_physical_observations(entry: JSONDict) -> JSONDict:
    entry = _casefold_fields(entry)
    observations: list[str] = []
    direct_pci = _native_namespace(entry.get("bdf"))
    if direct_pci is not None:
        observations.append(direct_pci)
    if "bus" in entry:
        bus = _casefold_fields(require_json_dict(entry["bus"], label="AMD native PCI bus"))
        nested_pci = _native_namespace(bus.get("bdf"))
        if nested_pci is not None and nested_pci not in observations:
            observations.append(nested_pci)
    return {
        "type": "amd",
        "uuid": _native_namespace(entry.get("uuid")),
        "pci_bdf_observations": observations,
    }


def _native_namespace(value: JSONValue) -> str | None:
    if value is None or value == "N/A":
        return None
    return require_canonical_trimmed_json_text(
        value, error_message="AMD native physical observation is invalid."
    )
