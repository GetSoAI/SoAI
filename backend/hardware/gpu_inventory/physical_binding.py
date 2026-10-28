"""SoAI - Observed GPU physical identity binding [backend/hardware/gpu_inventory/physical_binding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_identity_normalization import observed_pci_bdf_conflicts
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingResult,
    GPUPhysicalBindingState,
    GPUPhysicalDevice,
    GPUPhysicalIdentity,
    compare_gpu_physical_identities,
)
from core.hardware.gpu_physical_observations import (
    read_gpu_pci_observations,
    read_gpu_physical_identity,
    read_gpu_platform_observations,
    read_gpu_vendor,
)
from core.validation.numbers import coerce_int_from_json
from core.validation.strings import coerce_optional_trimmed_str
from hardware.gpu_inventory.physical_observations import invalid_gpu_candidate_claims_target

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "GPUInventoryJoins",
    "gpu_entry_accepts_device_id",
    "mark_gpu_inventory_bindings",
    "match_gpu_inventory_sources",
    "match_gpu_physical_identity",
    "resolve_gpu_physical_binding",
    "retain_gpu_native_aliases",
)


@dataclass(frozen=True, slots=True)
class GPUInventoryJoins:
    pairs: tuple[tuple[int, int], ...]
    baseline_results: tuple[GPUPhysicalBindingResult, ...]
    native_results: tuple[GPUPhysicalBindingResult, ...]


def match_gpu_physical_identity(selected: JSONDict, candidate: JSONDict) -> GPUPhysicalBindingState:
    try:
        selected_identity = read_gpu_physical_identity(selected)
        candidate_identity = read_gpu_physical_identity(candidate)
        selected_vendor = read_gpu_vendor(selected)
        candidate_vendor = read_gpu_vendor(candidate)
    except ValidationError:
        return GPUPhysicalBindingState.INVALID_RESPONSE
    vendor_conflict = (
        selected_vendor is not None
        and candidate_vendor is not None
        and selected_vendor.casefold() != candidate_vendor.casefold()
    )
    relation = (
        GPUPhysicalBindingState.IDENTITY_UNAVAILABLE
        if selected_identity is None or candidate_identity is None
        else compare_gpu_physical_identities(selected_identity, candidate_identity)
    )
    if relation == GPUPhysicalBindingState.IDENTITY_UNAVAILABLE:
        return (
            GPUPhysicalBindingState.DEVICE_UNAVAILABLE
            if vendor_conflict
            else GPUPhysicalBindingState.IDENTITY_UNAVAILABLE
        )
    if relation == GPUPhysicalBindingState.DEVICE_UNAVAILABLE:
        return relation
    if (
        relation == GPUPhysicalBindingState.IDENTITY_CONFLICT
        or any(
            observed_pci_bdf_conflicts(first, second)
            for first in read_gpu_pci_observations(selected)
            for second in read_gpu_pci_observations(candidate)
        )
        or vendor_conflict
    ):
        return GPUPhysicalBindingState.IDENTITY_CONFLICT
    return GPUPhysicalBindingState.BOUND


def resolve_gpu_physical_binding(
    selected: JSONDict, candidates: list[JSONDict]
) -> GPUPhysicalBindingResult:
    try:
        selected_identity = read_gpu_physical_identity(selected)
    except ValidationError:
        return GPUPhysicalBindingResult(
            GPUPhysicalBindingState.INVALID_RESPONSE, None, "invalid_identity"
        )
    if selected_identity is None:
        return GPUPhysicalBindingResult(
            GPUPhysicalBindingState.IDENTITY_UNAVAILABLE, None, "identity_unavailable"
        )
    matches: list[JSONDict] = []
    conflicting = False
    incomparable = False
    for candidate in candidates:
        relation = match_gpu_physical_identity(selected, candidate)
        if (
            relation == GPUPhysicalBindingState.INVALID_RESPONSE
            and invalid_gpu_candidate_claims_target(selected, selected_identity, candidate)
        ):
            return GPUPhysicalBindingResult(
                GPUPhysicalBindingState.INVALID_RESPONSE, None, "invalid_roster_identity"
            )
        if relation == GPUPhysicalBindingState.IDENTITY_CONFLICT:
            conflicting = True
        elif relation == GPUPhysicalBindingState.IDENTITY_UNAVAILABLE:
            incomparable = True
        elif relation == GPUPhysicalBindingState.BOUND:
            matches.append(candidate)
    if conflicting or len(matches) > 1:
        return GPUPhysicalBindingResult(
            GPUPhysicalBindingState.IDENTITY_CONFLICT, None, "identity_conflict"
        )
    if not matches:
        if incomparable:
            return GPUPhysicalBindingResult(
                GPUPhysicalBindingState.IDENTITY_UNAVAILABLE, None, "identity_unavailable"
            )
        return GPUPhysicalBindingResult(
            GPUPhysicalBindingState.DEVICE_UNAVAILABLE, None, "device_unavailable"
        )
    candidate = matches[0]
    identity = read_gpu_physical_identity(candidate)
    device_id = coerce_optional_trimmed_str(selected.get("device_id"))
    vendor = read_gpu_vendor(candidate)
    selected_driver, selected_compatible = read_gpu_platform_observations(selected)
    candidate_driver, candidate_compatible = read_gpu_platform_observations(candidate)
    if identity is None or device_id is None or vendor is None:
        return GPUPhysicalBindingResult(
            GPUPhysicalBindingState.INVALID_RESPONSE, None, "invalid_inventory_device"
        )
    return GPUPhysicalBindingResult(
        state=GPUPhysicalBindingState.BOUND,
        device=GPUPhysicalDevice(
            device_id=device_id,
            vendor=vendor,
            identity=GPUPhysicalIdentity(
                uuid=selected_identity.uuid or identity.uuid,
                pci_bdf_full=selected_identity.pci_bdf_full or identity.pci_bdf_full,
                native_device_path=selected_identity.native_device_path
                or identity.native_device_path,
                windows_pnp_instance_id=selected_identity.windows_pnp_instance_id
                or identity.windows_pnp_instance_id,
            ),
            gpu_index=coerce_int_from_json(candidate.get("index"), default=None),
            vendor_index=coerce_int_from_json(candidate.get("vendor_id"), default=None),
            pci_bdf_observations=tuple(
                dict.fromkeys(
                    read_gpu_pci_observations(selected) + read_gpu_pci_observations(candidate)
                )
            ),
            platform_driver=candidate_driver or selected_driver,
            platform_compatible=candidate_compatible or selected_compatible,
        ),
        reason_code=None,
    )


def mark_gpu_inventory_bindings(gpus: list[JSONDict]) -> None:
    for entry in gpus:
        device_id = coerce_optional_trimmed_str(entry.get("device_id"))
        if device_id is not None and sum(peer.get("device_id") == device_id for peer in gpus) > 1:
            entry["control_binding_state"] = GPUPhysicalBindingState.IDENTITY_CONFLICT.value
            entry["control_binding_reason"] = "ambiguous_device_id"
            continue
        if entry.get("control_binding_state") in (
            GPUPhysicalBindingState.IDENTITY_CONFLICT,
            GPUPhysicalBindingState.INVALID_RESPONSE,
        ):
            continue
        binding = resolve_gpu_physical_binding(entry, gpus)
        state, reason = binding.state, binding.reason_code
        if state == GPUPhysicalBindingState.BOUND:
            if entry.get("telemetry_available") is False:
                state, reason = (
                    GPUPhysicalBindingState.QUERY_UNAVAILABLE,
                    "vendor_runtime_unavailable",
                )
            elif (
                binding.device is None
                or binding.device.vendor_index is None
                or binding.device.vendor_index < 0
            ):
                state, reason = (
                    GPUPhysicalBindingState.QUERY_UNAVAILABLE,
                    "native_locator_unavailable",
                )
        entry["control_binding_state"] = state.value
        entry["control_binding_reason"] = reason


def match_gpu_inventory_sources(
    baselines: list[JSONDict], native_entries: list[JSONDict]
) -> GPUInventoryJoins:
    baseline_results = [resolve_gpu_physical_binding(entry, native_entries) for entry in baselines]
    native_results = [resolve_gpu_physical_binding(entry, baselines) for entry in native_entries]
    pairs: list[tuple[int, int]] = []
    for baseline_index, result in enumerate(baseline_results):
        if result.state != GPUPhysicalBindingState.BOUND:
            continue
        matches = [
            native_index
            for native_index, entry in enumerate(native_entries)
            if match_gpu_physical_identity(baselines[baseline_index], entry)
            == GPUPhysicalBindingState.BOUND
        ]
        if len(matches) != 1:
            continue
        native_index = matches[0]
        reverse = native_results[native_index]
        if reverse.state == GPUPhysicalBindingState.BOUND:
            pairs.append((baseline_index, native_index))
        else:
            baseline_results[baseline_index] = GPUPhysicalBindingResult(
                reverse.state, None, reverse.reason_code
            )
    for native_index, result in enumerate(native_results):
        if result.state == GPUPhysicalBindingState.BOUND and not any(
            native_index == pair[1] for pair in pairs
        ):
            native_results[native_index] = GPUPhysicalBindingResult(
                GPUPhysicalBindingState.IDENTITY_CONFLICT, None, "identity_conflict"
            )
    return GPUInventoryJoins(tuple(pairs), tuple(baseline_results), tuple(native_results))


def gpu_entry_accepts_device_id(entry: JSONDict, device_id: str) -> bool:
    if entry.get("device_id") == device_id:
        return True
    aliases = entry.get("device_id_aliases")
    if not isinstance(aliases, list) or device_id not in aliases:
        return False
    if entry.get("control_binding_state") in (
        GPUPhysicalBindingState.IDENTITY_CONFLICT,
        GPUPhysicalBindingState.INVALID_RESPONSE,
    ):
        return False
    try:
        return read_gpu_physical_identity(entry) is not None
    except ValidationError:
        return False


def retain_gpu_native_aliases(selected: JSONDict, native: JSONDict) -> None:
    if match_gpu_physical_identity(selected, native) != GPUPhysicalBindingState.BOUND:
        raise ValidationError("GPU aliases require a proved physical relation.")
    canonical_id = selected.get("device_id")
    aliases: list[str] = []
    for entry in (selected, native):
        values = entry.get("device_id_aliases", [])
        if not isinstance(values, list):
            raise ValidationError("GPU identity aliases must be a list.")
        for value in values:
            text = coerce_optional_trimmed_str(value)
            if text is None:
                raise ValidationError("GPU identity alias must be nonempty text.")
            if text != canonical_id and text not in aliases:
                aliases.append(text)
    native_id = coerce_optional_trimmed_str(native.get("device_id"))
    if native_id is not None and native_id != canonical_id and native_id not in aliases:
        aliases.append(native_id)
    if aliases:
        selected["device_id_aliases"] = aliases
