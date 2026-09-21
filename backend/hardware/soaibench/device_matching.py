"""SoAI - SoAIBench OpenCL device matching [backend/hardware/soaibench/device_matching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from hardware.gpu_inventory.identity import (
    normalize_identity_name,
    normalize_physical_pci_bdf,
    normalize_uuid,
)
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_devices import OpenCLGpuDevice
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.vendors.vendor_metadata import vendor_aliases
from hardware.vendors.vendor_types import AMD_VENDOR, INTEL_VENDOR, NVIDIA_VENDOR

__all__ = (
    "OpenCLDeviceMatch",
    "match_opencl_device",
)

AMD_OPENCL_PLATFORM_PRIORITY: tuple[tuple[str, ...], ...] = (
    ("rocm", "acceleratedparallelprocessing", "advancedmicrodevices"),
    ("rusticl",),
    ("clover",),
)
INTEL_OPENCL_PLATFORM_PRIORITY: tuple[tuple[str, ...], ...] = (("levelzero", "oneapi", "intel"),)
NVIDIA_OPENCL_PLATFORM_PRIORITY: tuple[tuple[str, ...], ...] = (("cuda", "nvidia"),)


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
    uuid_matches = [
        candidate
        for candidate in candidates
        if _same_uuid(identity.gpu_uuid, candidate.device_uuid)
    ]
    if len(uuid_matches) == 1:
        return OpenCLDeviceMatch(device=uuid_matches[0], match_basis="gpu_uuid")
    if len(uuid_matches) > 1:
        preferred = _preferred_platform_match(matching_vendor, uuid_matches)
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
        if _pci_candidates_share_physical_identity(pci_matches):
            preferred = _preferred_platform_match(matching_vendor, pci_matches)
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
        for candidate in vendor_matches
        if _same_name(matching_name, candidate.device_name)
    ]
    if len(named) == 1:
        return OpenCLDeviceMatch(device=named[0], match_basis="vendor_name")
    if len(named) > 1:
        preferred_candidates = _preferred_platform_candidates(matching_vendor, named)
        if len(preferred_candidates) == 1:
            return OpenCLDeviceMatch(
                device=preferred_candidates[0],
                match_basis="vendor_name_preferred_platform",
            )
        if identity.gpu_index is not None and preferred_candidates:
            indexed = [
                candidate
                for candidate in preferred_candidates
                if candidate.platform_device_index == identity.gpu_index
            ]
            if len(indexed) == 1:
                return OpenCLDeviceMatch(
                    device=indexed[0],
                    match_basis="vendor_name_preferred_platform_index",
                )
        raise SoAIBenchUnsupported(
            reason="opencl_device_match_ambiguous",
            message=_ambiguous_message("vendor and normalized GPU name", named),
        )
    if len(vendor_matches) == 1:
        return OpenCLDeviceMatch(device=vendor_matches[0], match_basis="vendor_single")
    if len(vendor_matches) > 1:
        preferred = _preferred_platform_match(matching_vendor, vendor_matches)
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


def _preferred_platform_match(
    identity_vendor: str | None,
    candidates: list[OpenCLGpuDevice],
) -> OpenCLGpuDevice | None:
    if len(candidates) < 2:
        return None
    scores = [(_platform_score(identity_vendor, candidate), candidate) for candidate in candidates]
    best_score = min(score for score, _candidate in scores)
    best_candidates = [candidate for score, candidate in scores if score == best_score]
    if best_score >= 100 or len(best_candidates) != 1:
        return None
    return best_candidates[0]


def _preferred_platform_candidates(
    identity_vendor: str | None,
    candidates: list[OpenCLGpuDevice],
) -> list[OpenCLGpuDevice]:
    scores = [(_platform_score(identity_vendor, candidate), candidate) for candidate in candidates]
    best_score = min(score for score, _candidate in scores)
    if best_score >= 100:
        return []
    return [candidate for score, candidate in scores if score == best_score]


def _platform_score(identity_vendor: str | None, candidate: OpenCLGpuDevice) -> int:
    aliases = vendor_aliases(identity_vendor or "")
    platform_text = normalize_identity_name(
        f"{candidate.platform_name} {candidate.platform_vendor} {candidate.device_vendor}",
    )
    if AMD_VENDOR in aliases:
        return _priority_score(platform_text, AMD_OPENCL_PLATFORM_PRIORITY)
    if INTEL_VENDOR in aliases:
        return _priority_score(platform_text, INTEL_OPENCL_PLATFORM_PRIORITY)
    if NVIDIA_VENDOR in aliases:
        return _priority_score(platform_text, NVIDIA_OPENCL_PLATFORM_PRIORITY)
    return 100


def _priority_score(platform_text: str, priorities: tuple[tuple[str, ...], ...]) -> int:
    for priority_index, markers in enumerate(priorities):
        if any(marker in platform_text for marker in markers):
            return priority_index
    return 100


def _same_vendor(
    identity_vendor: str | None,
    device_vendor: str,
    platform_vendor: str,
) -> bool:
    if identity_vendor is None:
        return True
    identity_aliases = vendor_aliases(identity_vendor)
    device_aliases = vendor_aliases(device_vendor) | vendor_aliases(platform_vendor)
    return bool(identity_aliases & device_aliases)


def _same_name(identity_name: str | None, opencl_name: str) -> bool:
    if identity_name is None:
        return False
    return normalize_identity_name(identity_name) == normalize_identity_name(opencl_name)


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


def _pci_candidates_share_physical_identity(candidates: list[OpenCLGpuDevice]) -> bool:
    domains = {
        normalized
        for candidate in candidates
        if (normalized := normalize_physical_pci_bdf(candidate.pci_bdf or "")).count(":") == 2
    }
    return len(domains) <= 1


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
