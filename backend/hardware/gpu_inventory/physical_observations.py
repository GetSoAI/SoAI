"""SoAI - Observed GPU identity facts [backend/hardware/gpu_inventory/physical_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_inventory_errors import gpu_inventory_query_failure
from core.hardware.gpu_physical_identity import GPUInventoryReadState, GPUPhysicalIdentity
from core.hardware.gpu_physical_observations import (
    gpu_pci_observation_fields,
    gpu_uuid_observation_fields,
    read_gpu_vendor,
)
from core.validation.strings import coerce_optional_trimmed_str
from hardware.vendors.vendor_types import AMD_VENDOR, INTEL_VENDOR

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "invalid_gpu_candidate_claims_target",
    "gpu_inventory_sources_incomplete",
    "require_gpu_discovery_available",
)


def require_gpu_discovery_available(payload: JSONDict) -> None:
    if not gpu_inventory_sources_incomplete(payload):
        return
    sources = payload.get("inventory_sources")
    outcomes = list(sources.values()) if isinstance(sources, dict) else []
    for source in outcomes:
        if isinstance(source, dict) and source.get("reason_code") in (
            "wmi_query_timeout",
            "platform_acquisition_deadline_expired",
            "pci_sysfs_acquisition_deadline_expired",
        ):
            raise gpu_inventory_query_failure("native_timeout")
    for source in outcomes:
        if not isinstance(source, dict):
            continue
        if source.get("reason_code") == "wmi_query_failed":
            raise gpu_inventory_query_failure("native_exit")
        if source.get("reason_code") == "wmi_response_empty":
            raise gpu_inventory_query_failure("empty_response")
        if source.get("state") == GPUInventoryReadState.PERMISSION_DENIED:
            raise gpu_inventory_query_failure("permission_denied")
        if source.get("state") == GPUInventoryReadState.INVALID_RESPONSE:
            raise gpu_inventory_query_failure("invalid_response")
        if source.get("state") == GPUInventoryReadState.RUNTIME_UNAVAILABLE:
            raise gpu_inventory_query_failure("runtime_unavailable")
    raise gpu_inventory_query_failure("query_unavailable")


def invalid_gpu_candidate_claims_target(
    selected: JSONDict, identity: GPUPhysicalIdentity, candidate: JSONDict
) -> bool:
    device_id = coerce_optional_trimmed_str(selected.get("device_id"))
    if device_id is not None and candidate.get("device_id") == device_id:
        return True
    if (
        identity.native_device_path is not None
        and candidate.get("native_device_path") == identity.native_device_path
    ):
        return True
    if (
        identity.windows_pnp_instance_id is not None
        and candidate.get("windows_pnp_instance_id") == identity.windows_pnp_instance_id
    ):
        return True
    for field in gpu_uuid_observation_fields(candidate):
        value = candidate.get(field)
        values = value if isinstance(value, list) and field == "gpu_uuid_observations" else [value]
        for observation in values:
            text = coerce_optional_trimmed_str(observation)
            if (
                identity.uuid is not None
                and text is not None
                and text.casefold() == identity.uuid.casefold()
            ):
                return True
    if identity.pci_bdf_full is None:
        return False
    selected_pci = normalize_observed_full_pci_bdf(identity.pci_bdf_full)
    for field in gpu_pci_observation_fields(candidate):
        value = candidate.get(field)
        values = value if isinstance(value, list) and field == "pci_bdf_observations" else [value]
        for observation in values:
            text = coerce_optional_trimmed_str(observation)
            if text is not None and normalize_observed_full_pci_bdf(text) == selected_pci:
                return True
    return False


def gpu_inventory_sources_incomplete(
    payload: JSONDict, *, retained_payload: JSONDict | None = None
) -> bool:
    sources = payload.get("inventory_sources")
    if sources is None:
        return False
    if not isinstance(sources, dict):
        raise ValidationError("GPU inventory source outcomes must be an object.")
    cim_source = sources.get("cim")
    rosters = [payload.get("gpus")]
    if retained_payload is not None:
        rosters.append(retained_payload.get("gpus"))
    nvidia_optional = (
        isinstance(cim_source, dict)
        and cim_source.get("state") == GPUInventoryReadState.OBSERVED
        and all(
            isinstance(roster, list)
            and all(
                isinstance(entry, dict) and read_gpu_vendor(entry) in (AMD_VENDOR, INTEL_VENDOR)
                for entry in roster
            )
            for roster in rosters
        )
    )
    incomplete = False
    for source_name, source in sources.items():
        if not isinstance(source, dict):
            raise ValidationError("GPU inventory source outcome must be an object.")
        state = source.get("state")
        if state not in (*GPUInventoryReadState, "unknown"):
            raise ValidationError("GPU inventory source outcome is invalid.")
        if (
            source_name == "nvidia"
            and nvidia_optional
            and state
            in (GPUInventoryReadState.QUERY_FAILED, GPUInventoryReadState.RUNTIME_UNAVAILABLE)
        ):
            continue
        if state not in (GPUInventoryReadState.OBSERVED, "unknown"):
            incomplete = True
    return incomplete


def select_gpu_physical_read_state(states: list[GPUInventoryReadState]) -> GPUInventoryReadState:
    if any(not isinstance(state, GPUInventoryReadState) for state in states):
        raise ValidationError("GPU physical acquisition has an invalid outcome state.")
    for state in (
        GPUInventoryReadState.INVALID_RESPONSE,
        GPUInventoryReadState.PERMISSION_DENIED,
        GPUInventoryReadState.QUERY_FAILED,
        GPUInventoryReadState.RUNTIME_UNAVAILABLE,
    ):
        if state in states:
            return state
    return GPUInventoryReadState.OBSERVED
