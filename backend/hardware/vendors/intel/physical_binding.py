"""SoAI - Retained Intel native discovery observations [backend/hardware/vendors/intel/physical_binding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState, GPUPhysicalIdentity
from core.hardware.gpu_physical_observations import read_gpu_physical_identity
from core.serialization.json_parsing import MAX_JSON_NESTING_DEPTH, parse_json_value
from core.types.json_value import require_json_dict
from core.validation.strict_integer import is_strict_int
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_inventory.physical_binding import match_gpu_physical_identity

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue


__all__ = (
    "IntelDiscoveryDevice",
    "IntelDiscoveryObservations",
    "acquire_intel_discovery_observations",
)


@dataclass(frozen=True, slots=True)
class IntelDiscoveryDevice:
    native_device_id: int
    identity: GPUPhysicalIdentity | None
    pci_bdf_observations: tuple[str, ...]
    device_state: str | None
    recovery_action: str | None


@dataclass(frozen=True, slots=True)
class IntelDiscoveryObservations:
    devices: tuple[IntelDiscoveryDevice, ...]


def acquire_intel_discovery_observations(
    executor: CommandExecutorProtocol, *, executable: str
) -> IntelDiscoveryObservations:
    if not isinstance(executable, str) or not executable or "\0" in executable:
        raise ValidationError("Intel discovery requires its explicit executable.")
    result = executor.execute(
        [executable, "discovery", "-j"], timeout=10, shell=False, use_sudo=False
    )
    if (
        not is_strict_int(result.return_code)
        or not isinstance(result.stdout, str)
        or not isinstance(result.stderr, str)
    ):
        raise ValidationError("Intel discovery response is invalid.")
    if result.return_code != 0:
        raise StateError(
            "Intel discovery query failed.",
            details={
                "return_code": result.return_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )
    payload = require_json_dict(
        parse_json_value(
            result.stdout,
            field="Intel discovery observations",
            max_depth=MAX_JSON_NESTING_DEPTH,
            reject_duplicate_keys=True,
        ),
        label="Intel discovery observations",
    )
    rows = payload.get("device_list")
    if not isinstance(rows, list):
        raise ValidationError("Intel discovery device_list is unavailable or invalid.")
    devices: list[IntelDiscoveryDevice] = []
    candidates: list[JSONDict] = []
    native_ids: set[int] = set()
    for value in rows:
        row = require_json_dict(value, label="Intel discovery device")
        native_id = row.get("device_id")
        if not is_strict_int(native_id) or native_id < 0:
            raise ValidationError("Intel discovery device identifier is invalid.")
        if native_id in native_ids:
            raise StateError("Intel discovery contains duplicate native device identifiers.")
        native_ids.add(native_id)
        pci = _observed_text(row.get("pci_bdf_address"))
        candidate: JSONDict = {
            "type": "intel",
            "uuid": _observed_text(row.get("uuid")),
            "pci_bdf_observations": [pci] if pci is not None else [],
        }
        identity = read_gpu_physical_identity(candidate)
        if any(
            match_gpu_physical_identity(candidate, previous)
            in (GPUPhysicalBindingState.BOUND, GPUPhysicalBindingState.IDENTITY_CONFLICT)
            for previous in candidates
        ):
            raise StateError("Intel discovery contains duplicate or conflicting physical facts.")
        devices.append(
            IntelDiscoveryDevice(
                native_id,
                identity,
                (pci,) if pci is not None else (),
                _observed_text(row.get("device_state")),
                _observed_text(row.get("recovery_action")),
            )
        )
        candidates.append(candidate)
    return IntelDiscoveryObservations(tuple(devices))


def _observed_text(value: JSONValue) -> str | None:
    if value is None:
        return None
    return require_canonical_trimmed_json_text(
        value, error_message="Intel discovery observation is invalid."
    )
