"""SoAI - SoAIBench OpenCL device matching [backend/hardware/soaibench/device_matching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.hardware.gpu_identity_normalization import is_specific_gpu_name, normalize_identity_name
from core.hardware.gpu_model_catalog import resolve_catalog_submission_identity
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_bindings import CL_DEVICE_TYPE_CUSTOM, CL_DEVICE_TYPE_GPU
from hardware.soaibench.opencl_device_info import OpenCLGpuDevice
from hardware.soaibench.opencl_physical_identity import (
    has_strong_opencl_identity,
    matching_opencl_pci_bdf,
    matching_opencl_uuid,
    opencl_candidate_evidence_conflicts,
    opencl_candidates_share_physical_identity,
    opencl_physical_evidence_conflicts,
)
from hardware.soaibench.opencl_platform_priority import (
    preferred_platform_match,
)
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.vendors.vendor_metadata import vendor_aliases

__all__ = (
    "OpenCLDeviceMatch",
    "STRONG_MATCH_BASES",
    "match_opencl_device",
    "opencl_vendor_matches",
)


STRONG_MATCH_BASES = (
    "gpu_uuid",
    "gpu_uuid_preferred_platform",
    "pci_bdf",
    "pci_bdf_preferred_platform",
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
    for candidate in candidates:
        if not (
            candidate.capabilities.device_type & CL_DEVICE_TYPE_GPU
            or candidate.capabilities.device_type == CL_DEVICE_TYPE_CUSTOM
        ):
            continue
        if (
            matching_opencl_uuid(identity.gpu_uuid, candidate.device_uuid)
            or matching_opencl_pci_bdf(identity.pci_bdf, candidate.pci_bdf)
        ) and opencl_physical_evidence_conflicts(identity, candidate):
            raise SoAIBenchUnsupported(
                reason="opencl_device_identity_conflict",
                message="OpenCL physical identity conflicts with the selected GPU.",
            )
    candidates = [
        candidate
        for candidate in candidates
        if candidate.capabilities.device_type & CL_DEVICE_TYPE_GPU
        or (
            candidate.capabilities.device_type == CL_DEVICE_TYPE_CUSTOM
            and has_strong_opencl_identity(identity, candidate.device_uuid, candidate.pci_bdf)
            and normalize_identity_name(matching_vendor or "") not in {"", "unknown"}
            and opencl_vendor_matches(matching_vendor, candidate.device_vendor, "")
        )
    ]
    physical_matches = [
        candidate
        for candidate in candidates
        if matching_opencl_uuid(identity.gpu_uuid, candidate.device_uuid)
        or matching_opencl_pci_bdf(identity.pci_bdf, candidate.pci_bdf)
    ]
    if opencl_candidate_evidence_conflicts(physical_matches):
        raise SoAIBenchUnsupported(
            reason="opencl_device_match_ambiguous",
            message=_ambiguous_message("physical identity", physical_matches),
        )
    if any(
        candidate.capabilities.device_type & CL_DEVICE_TYPE_GPU
        and has_strong_opencl_identity(identity, candidate.device_uuid, candidate.pci_bdf)
        for candidate in physical_matches
    ):
        candidates = [
            candidate
            for candidate in candidates
            if candidate.capabilities.device_type & CL_DEVICE_TYPE_GPU
        ]
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
        if matching_opencl_uuid(identity.gpu_uuid, candidate.device_uuid)
    ]
    native_uuid_matches = [
        candidate
        for candidate in uuid_matches
        if candidate.capabilities.device_type & CL_DEVICE_TYPE_GPU
    ]
    uuid_matches = native_uuid_matches or uuid_matches
    if len(uuid_matches) == 1:
        return OpenCLDeviceMatch(device=uuid_matches[0], match_basis="gpu_uuid")
    if len(uuid_matches) > 1:
        preferred = (
            preferred_platform_match(matching_vendor, uuid_matches)
            if opencl_candidates_share_physical_identity(uuid_matches)
            else None
        )
        if preferred is not None:
            return OpenCLDeviceMatch(device=preferred, match_basis="gpu_uuid_preferred_platform")
        raise SoAIBenchUnsupported(
            reason="opencl_device_match_ambiguous",
            message=_ambiguous_message("UUID", uuid_matches),
        )
    pci_matches = [
        candidate
        for candidate in candidates
        if matching_opencl_pci_bdf(identity.pci_bdf, candidate.pci_bdf)
    ]
    native_pci_matches = [
        candidate
        for candidate in pci_matches
        if candidate.capabilities.device_type & CL_DEVICE_TYPE_GPU
    ]
    pci_matches = native_pci_matches or pci_matches
    if len(pci_matches) == 1:
        return OpenCLDeviceMatch(device=pci_matches[0], match_basis="pci_bdf")
    if len(pci_matches) > 1:
        if opencl_candidates_share_physical_identity(pci_matches):
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
        if opencl_vendor_matches(
            matching_vendor, candidate.device_vendor, candidate.platform_vendor
        )
    ]
    named = [
        candidate
        for candidate in candidates
        if normalize_identity_name(candidate.device_name) in matching_name_keys
        and (
            opencl_vendor_matches(
                matching_vendor, candidate.device_vendor, candidate.platform_vendor
            )
            or _vendor_evidence_missing(candidate)
        )
    ]
    if any(opencl_physical_evidence_conflicts(identity, candidate) for candidate in named):
        raise SoAIBenchUnsupported(
            reason="opencl_device_identity_conflict",
            message="OpenCL physical identity conflicts with the selected GPU.",
        )
    if len(named) == 1:
        return OpenCLDeviceMatch(device=named[0], match_basis="vendor_name")
    if len(named) > 1:
        if opencl_candidates_share_physical_identity(named):
            preferred = preferred_platform_match(matching_vendor, named)
        else:
            preferred = None
        if preferred is not None:
            return OpenCLDeviceMatch(
                device=preferred,
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
    if any(opencl_physical_evidence_conflicts(identity, candidate) for candidate in vendor_matches):
        raise SoAIBenchUnsupported(
            reason="opencl_device_identity_conflict",
            message="OpenCL physical identity conflicts with the selected GPU.",
        )
    if len(vendor_matches) == 1:
        return OpenCLDeviceMatch(device=vendor_matches[0], match_basis="vendor_single")
    if len(vendor_matches) > 1:
        preferred = (
            preferred_platform_match(matching_vendor, vendor_matches)
            if opencl_candidates_share_physical_identity(vendor_matches)
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


def opencl_vendor_matches(
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
