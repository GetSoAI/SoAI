"""SoAI - SoAIBench OpenCL platform preference policy [backend/hardware/soaibench/opencl_platform_priority.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from hardware.gpu_inventory.identity import normalize_identity_name
from hardware.soaibench.opencl_devices import OpenCLGpuDevice
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
    return preferred[0] if len(preferred) == 1 else None


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
