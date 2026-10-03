"""SoAI - SoAIBench OpenCL device matching [backend/hardware/soaibench/device_matching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.hardware.gpu_identity_normalization import is_specific_gpu_name, normalize_identity_name
from core.hardware.gpu_model_catalog import resolve_catalog_submission_identity
from hardware.gpu_inventory.identity import (
    normalize_physical_pci_bdf,
    normalize_uuid,
)
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_devices import OpenCLGpuDevice
from hardware.soaibench.opencl_platform_priority import (
    preferred_platform_candidates,
    preferred_platform_match,
)
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.vendors.vendor_metadata import vendor_aliases

__all__ = (
    "OpenCLDeviceMatch",
    "match_opencl_device",
)


@dataclass(frozen=True, slots=True)
class OpenCLDeviceMatch:
    device: OpenCLGpuDevice
    match_basis: str


def match_opencl_device(
    identity: SoAIBenchGpuIdentity,
    candidates: list[OpenCLGpuDevice],
) -> OpenCLDeviceMatch:
    matching_vendor = identity.raw_vendor or identity.vendor
    matching_name = identity.raw_gpu_name or identity.gpu_name
    matching_name_keys: set[str] = set()
    if matching_name is not None and is_specific_gpu_name(matching_name):
        normalized_name = normalize_identity_name(matching_name)
        if normalized_name:
            matching_name_keys.add(normalized_name)
    catalog_model = resolve_catalog_submission_identity(
        matching_name, identity.gpu_model_key, matching_vendor
    ).model
    if catalog_model is not None:
        matching_name_keys.update(
            normalize_identity_name(name) for name in (catalog_model.name, *catalog_model.aliases)
        )
    uuid_matches = [
        candidate
        for candidate in candidates
        if _same_uuid(identity.gpu_uuid, candidate.device_uuid)
    ]
    if any(
        _pci_evidence_contradicts(identity.pci_bdf, candidate.pci_bdf) for candidate in uuid_matches
    ):
        raise SoAIBenchUnsupported(
            reason="opencl_device_identity_conflict",
            message="OpenCL PCI evidence conflicts with the selected GPU UUID identity.",
        )
    if len(uuid_matches) == 1:
        return OpenCLDeviceMatch(device=uuid_matches[0], match_basis="gpu_uuid")
    if len(uuid_matches) > 1:
        preferred = (
            preferred_platform_match(matching_vendor, uuid_matches)
            if _candidates_share_physical_identity(uuid_matches)
            else None
        )
        if preferred is not None:
            return OpenCLDeviceMatch(device=preferred, match_basis="gpu_uuid_preferred_platform")
        raise SoAIBenchUnsupported(
            reason="opencl_device_match_ambiguous",
            message=_ambiguous_message("UUID", uuid_matches),
        )
    pci_matches = [
        candidate for candidate in candidates if _same_pci_bdf(identity.pci_bdf, candidate.pci_bdf)
    ]
    consistent_pci_matches = [
        candidate
        for candidate in pci_matches
        if not _uuid_evidence_contradicts(identity.gpu_uuid, candidate.device_uuid)
    ]
    if pci_matches and not consistent_pci_matches:
        raise SoAIBenchUnsupported(
            reason="opencl_device_identity_conflict",
            message="OpenCL UUID evidence conflicts with the selected GPU PCI identity.",
        )
    pci_matches = consistent_pci_matches
    if len(pci_matches) == 1:
        return OpenCLDeviceMatch(device=pci_matches[0], match_basis="pci_bdf")
    if len(pci_matches) > 1:
        if _candidates_share_physical_identity(pci_matches):
            preferred = preferred_platform_match(matching_vendor, pci_matches)
            if preferred is not None:
                return OpenCLDeviceMatch(
                    device=preferred,
                    match_basis="pci_bdf_preferred_platform",
                )
        raise SoAIBenchUnsupported(
            reason="opencl_device_match_ambiguous",
            message=_ambiguous_message("PCI address", pci_matches),
        )
    vendor_matches = [
        candidate
        for candidate in candidates
        if _same_vendor(matching_vendor, candidate.device_vendor, candidate.platform_vendor)
    ]
    named = [
        candidate
        for candidate in candidates
        if normalize_identity_name(candidate.device_name) in matching_name_keys
        and (
            _same_vendor(matching_vendor, candidate.device_vendor, candidate.platform_vendor)
            or _vendor_evidence_missing(candidate)
        )
    ]
    if any(_physical_evidence_contradicts(identity, candidate) for candidate in named):
        raise SoAIBenchUnsupported(
            reason="opencl_device_identity_conflict",
            message="OpenCL physical identity conflicts with the selected GPU.",
        )
    if len(named) == 1:
        return OpenCLDeviceMatch(device=named[0], match_basis="vendor_name")
    if len(named) > 1:
        if _candidates_share_physical_identity(named):
            preferred_candidates = preferred_platform_candidates(matching_vendor, named)
        else:
            preferred_candidates = []
        if len(preferred_candidates) == 1:
            return OpenCLDeviceMatch(
                device=preferred_candidates[0],
                match_basis="vendor_name_preferred_platform",
            )
        raise SoAIBenchUnsupported(
            reason="opencl_device_match_ambiguous",
            message=_ambiguous_message("vendor and normalized GPU name", named),
        )
    if matching_name is not None:
        raise SoAIBenchUnsupported(
            reason="opencl_device_match_missing",
            message=_missing_message(identity),
        )
    if any(_physical_evidence_contradicts(identity, candidate) for candidate in vendor_matches):
        raise SoAIBenchUnsupported(
            reason="opencl_device_identity_conflict",
            message="OpenCL physical identity conflicts with the selected GPU.",
        )
    if len(vendor_matches) == 1:
        return OpenCLDeviceMatch(device=vendor_matches[0], match_basis="vendor_single")
    if len(vendor_matches) > 1:
        preferred = (
            preferred_platform_match(matching_vendor, vendor_matches)
            if _candidates_share_physical_identity(vendor_matches)
            else None
        )
        if preferred is not None:
            return OpenCLDeviceMatch(device=preferred, match_basis="vendor_preferred_platform")
        raise SoAIBenchUnsupported(
            reason="opencl_device_match_ambiguous",
            message=_ambiguous_message("vendor", vendor_matches),
        )
    raise SoAIBenchUnsupported(
        reason="opencl_device_match_missing",
        message=_missing_message(identity),
    )


def _same_vendor(
    identity_vendor: str | None,
    device_vendor: str,
    platform_vendor: str,
) -> bool:
    if identity_vendor is None or normalize_identity_name(identity_vendor) in {"", "unknown"}:
        return True
    identity_aliases = vendor_aliases(identity_vendor)
    device_aliases = vendor_aliases(device_vendor) | vendor_aliases(platform_vendor)
    return bool((identity_aliases - {""}) & (device_aliases - {""}))


def _vendor_evidence_missing(candidate: OpenCLGpuDevice) -> bool:
    return all(
        normalize_identity_name(value) in {"", "unknown"}
        for value in (candidate.device_vendor, candidate.platform_vendor)
    )


def _physical_evidence_contradicts(
    identity: SoAIBenchGpuIdentity, candidate: OpenCLGpuDevice
) -> bool:
    return _uuid_evidence_contradicts(
        identity.gpu_uuid, candidate.device_uuid
    ) or _pci_evidence_contradicts(identity.pci_bdf, candidate.pci_bdf)


def _pci_evidence_contradicts(identity_pci: str | None, device_pci: str | None) -> bool:
    if identity_pci is None or device_pci is None:
        return False
    identity_address = normalize_physical_pci_bdf(identity_pci)
    device_address = normalize_physical_pci_bdf(device_pci)
    return bool(identity_address and device_address) and not _same_pci_bdf(
        identity_address, device_address
    )


def _candidates_share_physical_identity(candidates: list[OpenCLGpuDevice]) -> bool:
    uuids = [
        normalized
        for candidate in candidates
        if candidate.device_uuid is not None
        and (normalized := _comparable_uuid(candidate.device_uuid)) is not None
    ]
    addresses = [normalize_physical_pci_bdf(candidate.pci_bdf or "") for candidate in candidates]
    full_addresses = [address for address in addresses if address.count(":") == 2]
    if len(set(uuids)) > 1 or len(set(full_addresses)) > 1:
        return False
    return len(uuids) == len(candidates) or len(full_addresses) == len(candidates)


def _same_uuid(identity_uuid: str | None, device_uuid: str | None) -> bool:
    if identity_uuid is None or device_uuid is None:
        return False
    normalized_identity = _comparable_uuid(identity_uuid)
    normalized_device = _comparable_uuid(device_uuid)
    return normalized_identity is not None and normalized_identity == normalized_device


def _same_pci_bdf(identity_pci_bdf: str | None, device_pci_bdf: str | None) -> bool:
    if identity_pci_bdf is None or device_pci_bdf is None:
        return False
    normalized_identity = normalize_physical_pci_bdf(identity_pci_bdf)
    normalized_device = normalize_physical_pci_bdf(device_pci_bdf)
    if not normalized_identity or not normalized_device:
        return False
    identity_has_domain = normalized_identity.count(":") == 2
    device_has_domain = normalized_device.count(":") == 2
    if identity_has_domain and device_has_domain:
        return normalized_identity == normalized_device
    identity_suffix = (
        normalized_identity.split(":", 1)[1] if identity_has_domain else normalized_identity
    )
    device_suffix = normalized_device.split(":", 1)[1] if device_has_domain else normalized_device
    return identity_suffix == device_suffix


def _uuid_evidence_contradicts(identity_uuid: str | None, device_uuid: str | None) -> bool:
    if identity_uuid is None or device_uuid is None:
        return False
    normalized_identity = _comparable_uuid(identity_uuid)
    normalized_device = _comparable_uuid(device_uuid)
    return (
        normalized_identity is not None
        and normalized_device is not None
        and normalized_identity != normalized_device
    )


def _comparable_uuid(value: str) -> str | None:
    normalized = normalize_uuid(value)
    if len(normalized) != 32 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        return None
    return normalized


def _ambiguous_message(label: str, candidates: list[OpenCLGpuDevice]) -> str:
    return (
        f"Multiple OpenCL GPU devices match the selected SoAI GPU {label}. "
        f"Candidates: {', '.join(_candidate_summary(candidate) for candidate in candidates)}."
    )


def _missing_message(identity: SoAIBenchGpuIdentity) -> str:
    selected_identity = ", ".join(
        part
        for part in (
            _identity_summary_part("vendor", identity.vendor),
            _identity_summary_part("name", identity.gpu_name),
            _identity_summary_part("gpu_uuid", identity.gpu_uuid),
            _identity_summary_part("pci_bdf", identity.pci_bdf),
            _identity_summary_part(
                "ordinal",
                str(identity.gpu_index) if identity.gpu_index is not None else None,
            ),
        )
        if part
    )
    return f"No OpenCL GPU device matches the selected SoAI GPU. Selected identity: {selected_identity}."


def _candidate_summary(candidate: OpenCLGpuDevice) -> str:
    return ", ".join(
        part
        for part in (
            _identity_summary_part("vendor", candidate.device_vendor),
            _identity_summary_part("name", candidate.device_name),
            _identity_summary_part("gpu_uuid", candidate.device_uuid),
            _identity_summary_part("pci_bdf", candidate.pci_bdf),
            _identity_summary_part("ordinal", str(candidate.ordinal)),
            _identity_summary_part("platform_device_index", str(candidate.platform_device_index)),
        )
        if part
    )


def _identity_summary_part(label: str, value: str | None) -> str:
    if value is None or not value:
        return ""
    return f"{label}={value}"
