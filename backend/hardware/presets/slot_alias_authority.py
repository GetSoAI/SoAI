"""SoAI - Non-destructive GPU slot alias reconciliation [backend/hardware/presets/slot_alias_authority.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.hardware.gpu_slot_failures import GPUSlotAliasConflictError
from core.types.json import JSONDict
from core.types.json_value import require_json_dict
from hardware.control.profiles import default_boot_payload
from hardware.presets.inventory_snapshot import canonical_gpu_inventory, resolve_inventory_device_id
from hardware.presets.slot_alias_history import reassign_alias_history
from hardware.presets.slot_alias_profiles import consolidate_alias_profiles
from hardware.presets.slot_control_state import is_device_entry_empty
from hardware.presets.slot_format import has_unrecognized_gpu_slot_state

__all__ = (
    "GpuSlotAliasReconciliation",
    "normalize_slot_aliases",
    "require_slot_alias_authority",
    "require_slot_mutation_authority",
)


@dataclass(frozen=True, slots=True)
class GpuSlotAliasReconciliation:
    protected_device_ids: frozenset[str]
    conflicting_device_ids: frozenset[str]


def _state(entry: JSONDict) -> JSONDict:
    return {
        "slots": entry.get("slots", {}),
        "boot": {
            **default_boot_payload(),
            **require_json_dict(entry.get("boot", {}), label="GPU slot boot"),
        },
        "field_modes": entry.get("field_modes", {}),
        "applied_settings": entry.get("applied_settings", {}),
        "unverified_control_fields": entry.get("unverified_control_fields", []),
    }


def normalize_slot_aliases(
    payload: JSONDict, inventory: dict[str, JSONDict]
) -> GpuSlotAliasReconciliation:
    devices = payload.get("devices")
    if not isinstance(devices, dict):
        return GpuSlotAliasReconciliation(frozenset(), frozenset())
    groups: dict[str, list[str]] = {
        device_id: [] for device_id in canonical_gpu_inventory(inventory)
    }
    protected: set[str] = set()
    conflicts: set[str] = set()
    for device_id in devices:
        try:
            canonical = resolve_inventory_device_id(inventory, device_id)
        except ValidationError:
            protected.add(device_id)
            conflicts.add(device_id)
            selected = inventory.get(device_id)
            conflicted_canonical = selected.get("device_id") if selected is not None else None
            if isinstance(conflicted_canonical, str):
                protected.add(conflicted_canonical)
                conflicts.add(conflicted_canonical)
            continue
        if canonical is not None:
            groups[canonical].append(device_id)
    recovery = payload.get("recovery")
    for canonical, source_ids in groups.items():
        has_alias_sources = any(source_id != canonical for source_id in source_ids)
        entries = [(source_id, devices[source_id]) for source_id in source_ids]
        if any(not isinstance(entry, dict) for _, entry in entries):
            protected.update((canonical, *source_ids))
            conflicts.add(canonical)
            continue
        sources = [(source_id, entry) for source_id, entry in entries if isinstance(entry, dict)]
        if (
            isinstance(recovery, dict)
            and has_alias_sources
            and any(source_id in recovery for source_id in (canonical, *source_ids))
        ):
            protected.update((canonical, *source_ids))
            conflicts.add(canonical)
            continue
        if not has_alias_sources:
            if any(has_unrecognized_gpu_slot_state(entry) for _, entry in sources):
                protected.update((canonical, *source_ids))
            continue
        meaningful = [
            (source_id, entry) for source_id, entry in sources if not is_device_entry_empty(entry)
        ]
        if meaningful and (
            any(has_unrecognized_gpu_slot_state(entry) for _, entry in sources)
            or any(_state(entry) != _state(meaningful[0][1]) for _, entry in meaningful)
        ):
            devices[canonical] = consolidate_alias_profiles(payload, canonical, sources)
        elif meaningful:
            authority = copy.deepcopy(meaningful[0][1])
            authority["device_id"] = canonical
            devices[canonical] = authority
        for source_id, _ in sources:
            if source_id != canonical:
                del devices[source_id]
    history = require_json_dict(payload.get("alias_history", {}), label="GPU alias history")
    for source_id in history:
        try:
            canonical = resolve_inventory_device_id(inventory, source_id)
        except ValidationError:
            protected.add(source_id)
            conflicts.add(source_id)
            continue
        if canonical is not None:
            reassign_alias_history(payload, source_id, canonical)
    return GpuSlotAliasReconciliation(frozenset(protected), frozenset(conflicts))


def require_slot_alias_authority(
    payload: JSONDict, inventory: dict[str, JSONDict], device_id: str
) -> GpuSlotAliasReconciliation:
    reconciliation = normalize_slot_aliases(payload, inventory)
    if device_id in reconciliation.conflicting_device_ids:
        raise GPUSlotAliasConflictError(
            "Saved GPU aliases do not have a single recognized authority.",
            details={"device_id": device_id, "reason_code": "gpu_slot_alias_conflict"},
        )
    return reconciliation


def require_slot_mutation_authority(
    reconciliation: GpuSlotAliasReconciliation, device_id: str
) -> None:
    if device_id in reconciliation.protected_device_ids:
        raise GPUSlotAliasConflictError(
            "Saved GPU profile contains unrecognized state that cannot be overwritten safely.",
            details={"device_id": device_id, "reason_code": "unrecognized_gpu_slot_state"},
        )
