"""SoAI - OpenCL physical identity agreement [backend/hardware/soaibench/opencl_physical_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.hardware.gpu_identity_normalization import (
    normalize_observed_full_pci_bdf,
    normalize_physical_pci_bdf,
    observed_pci_bdf_components,
    observed_pci_bdf_conflicts,
)
from hardware.gpu_inventory.identity import normalize_uuid
from hardware.soaibench.opencl_device_info import OpenCLGpuDevice
from hardware.soaibench.types import SoAIBenchGpuIdentity

__all__ = (
    "opencl_physical_evidence_conflicts",
    "opencl_pci_evidence_conflicts",
    "opencl_candidates_share_physical_identity",
    "opencl_candidate_evidence_conflicts",
    "matching_opencl_uuid",
    "matching_opencl_pci_bdf",
    "opencl_uuid_evidence_conflicts",
    "comparable_opencl_uuid",
    "has_strong_opencl_identity",
)


def opencl_physical_evidence_conflicts(
    identity: SoAIBenchGpuIdentity, candidate: OpenCLGpuDevice
) -> bool:
    return opencl_uuid_evidence_conflicts(
        identity.gpu_uuid, candidate.device_uuid
    ) or opencl_pci_evidence_conflicts(identity.pci_bdf, candidate.pci_bdf)


def opencl_pci_evidence_conflicts(identity_pci: str | None, device_pci: str | None) -> bool:
    if identity_pci is None or device_pci is None:
        return False
    return observed_pci_bdf_conflicts(
        _opencl_pci_address(identity_pci), _opencl_pci_address(device_pci)
    )


def opencl_candidates_share_physical_identity(candidates: list[OpenCLGpuDevice]) -> bool:
    uuids = [
        normalized
        for candidate in candidates
        if candidate.device_uuid is not None
        and (normalized := comparable_opencl_uuid(candidate.device_uuid)) is not None
    ]
    addresses = [
        _opencl_pci_address(candidate.pci_bdf) for candidate in candidates if candidate.pci_bdf
    ]
    full_addresses = [
        address for value in addresses if (address := normalize_observed_full_pci_bdf(value))
    ]
    if opencl_candidate_evidence_conflicts(candidates):
        return False
    return len(uuids) == len(candidates) or len(full_addresses) == len(candidates)


def opencl_candidate_evidence_conflicts(candidates: list[OpenCLGpuDevice]) -> bool:
    return any(
        opencl_uuid_evidence_conflicts(first.device_uuid, second.device_uuid)
        or opencl_pci_evidence_conflicts(first.pci_bdf, second.pci_bdf)
        for position, first in enumerate(candidates)
        for second in candidates[position + 1 :]
    )


def matching_opencl_uuid(identity_uuid: str | None, device_uuid: str | None) -> bool:
    if identity_uuid is None or device_uuid is None:
        return False
    normalized_identity = comparable_opencl_uuid(identity_uuid)
    normalized_device = comparable_opencl_uuid(device_uuid)
    return normalized_identity is not None and normalized_identity == normalized_device


def matching_opencl_pci_bdf(identity_pci_bdf: str | None, device_pci_bdf: str | None) -> bool:
    if identity_pci_bdf is None or device_pci_bdf is None:
        return False
    identity = observed_pci_bdf_components(_opencl_pci_address(identity_pci_bdf))
    device = observed_pci_bdf_components(_opencl_pci_address(device_pci_bdf))
    if identity is None or device is None:
        return False
    return (
        (identity[0] is None or device[0] is None or identity[0] == device[0])
        and identity[1:3] == device[1:3]
        and (identity[3] or 0) == (device[3] or 0)
    )


def _opencl_pci_address(value: str) -> str:
    if observed_pci_bdf_components(value) is not None:
        return value
    if value.count(":") == 1:
        return normalize_physical_pci_bdf(value)
    return ""


def opencl_uuid_evidence_conflicts(identity_uuid: str | None, device_uuid: str | None) -> bool:
    if identity_uuid is None or device_uuid is None:
        return False
    normalized_identity = comparable_opencl_uuid(identity_uuid)
    normalized_device = comparable_opencl_uuid(device_uuid)
    return (
        normalized_identity is not None
        and normalized_device is not None
        and normalized_identity != normalized_device
    )


def comparable_opencl_uuid(value: str) -> str | None:
    normalized = normalize_uuid(value)
    if (
        normalized == "0" * 32
        or len(normalized) != 32
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        return None
    return normalized


def has_strong_opencl_identity(
    identity: SoAIBenchGpuIdentity, device_uuid: str | None, pci_bdf: str | None
) -> bool:
    selected_uuid = comparable_opencl_uuid(identity.gpu_uuid or "")
    observed_uuid = comparable_opencl_uuid(device_uuid or "")
    uuid_matches = (
        selected_uuid is not None and selected_uuid != "0" * 32 and selected_uuid == observed_uuid
    )
    selected_pci = normalize_observed_full_pci_bdf(identity.pci_bdf or "")
    observed_pci = normalize_observed_full_pci_bdf(pci_bdf or "")
    return uuid_matches or bool(selected_pci and selected_pci == observed_pci)
