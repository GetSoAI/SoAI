"""SoAI - SoAIBench OpenCL platform preference policy [backend/hardware/soaibench/opencl_platform_priority.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from hardware.gpu_inventory.identity import normalize_identity_name
from hardware.soaibench.opencl_device_info import OpenCLGpuDevice
from hardware.vendors.vendor_metadata import vendor_aliases
from hardware.vendors.vendor_types import AMD_VENDOR, INTEL_VENDOR, NVIDIA_VENDOR

__all__ = ("preferred_platform_candidates", "preferred_platform_match")

AMD_OPENCL_PLATFORM_PRIORITY: tuple[tuple[str, ...], ...] = (
    ("rocm", "acceleratedparallelprocessing", "advancedmicrodevices"),
    ("rusticl",),
    ("clover",),
)
INTEL_OPENCL_PLATFORM_PRIORITY: tuple[tuple[str, ...], ...] = (("levelzero", "oneapi", "intel"),)
NVIDIA_OPENCL_PLATFORM_PRIORITY: tuple[tuple[str, ...], ...] = (("cuda", "nvidia"),)


def preferred_platform_match(
    identity_vendor: str | None,
    candidates: list[OpenCLGpuDevice],
) -> OpenCLGpuDevice | None:
    if len(candidates) < 2:
        return None
    preferred = preferred_platform_candidates(identity_vendor, candidates)
    if len(preferred) == 1:
        return preferred[0]
    if not preferred:
        return None
    first_key = _runtime_equivalence_key(identity_vendor, preferred[0])
    if first_key is None or any(
        _runtime_equivalence_key(identity_vendor, candidate) != first_key
        for candidate in preferred[1:]
    ):
        return None
    return min(preferred, key=_runtime_metadata_order)


def preferred_platform_candidates(
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
        f"{candidate.platform_name} {candidate.platform_vendor}",
    )
    return _vendor_platform_score(aliases, platform_text)


def _vendor_platform_score(aliases: set[str], platform_text: str) -> int:
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


def _runtime_equivalence_key(
    identity_vendor: str | None,
    candidate: OpenCLGpuDevice,
) -> tuple[str, str, str, str, str, str, str, int, int] | None:
    selected_vendors = vendor_aliases(identity_vendor or "") & {
        AMD_VENDOR,
        INTEL_VENDOR,
        NVIDIA_VENDOR,
    }
    if not selected_vendors or not all(
        vendor_aliases(value) & selected_vendors
        for value in (candidate.device_vendor, candidate.platform_vendor)
    ):
        return None
    platform_name = normalize_identity_name(candidate.platform_name)
    if _vendor_platform_score(selected_vendors, platform_name) >= 100:
        return None
    platform_vendor = normalize_identity_name(candidate.platform_vendor)
    device_name = normalize_identity_name(candidate.device_name)
    device_vendor = normalize_identity_name(candidate.device_vendor)
    platform_version = candidate.platform_version.strip()
    device_version = candidate.device_version.strip()
    driver_version = candidate.driver_version.strip()
    if (
        any(
            value.lower() in {"", "unknown"}
            for value in (
                platform_name,
                platform_vendor,
                device_name,
                device_vendor,
                platform_version,
                device_version,
                driver_version,
            )
        )
        or not 0 < candidate.max_alloc_bytes <= candidate.global_mem_bytes
    ):
        return None
    return (
        platform_name,
        platform_vendor,
        device_name,
        device_vendor,
        platform_version,
        device_version,
        driver_version,
        candidate.global_mem_bytes,
        candidate.max_alloc_bytes,
    )


def _runtime_metadata_order(candidate: OpenCLGpuDevice) -> tuple[str, ...]:
    return (
        candidate.platform_name,
        candidate.platform_vendor,
        candidate.platform_version,
        candidate.device_name,
        candidate.device_vendor,
        candidate.device_version,
        candidate.driver_version,
    )
