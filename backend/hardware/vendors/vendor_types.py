"""SoAI - Canonical GPU vendor identifiers [backend/hardware/vendors/vendor_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "AMD_VENDOR",
    "GPU_VENDOR_TYPES",
    "INTEL_VENDOR",
    "NVIDIA_VENDOR",
    "UNKNOWN_VENDOR",
    "vendor_hints_or_all",
)

NVIDIA_VENDOR = "nvidia"
AMD_VENDOR = "amd"
INTEL_VENDOR = "intel"
UNKNOWN_VENDOR = "unknown"
GPU_VENDOR_TYPES: tuple[str, ...] = (NVIDIA_VENDOR, AMD_VENDOR, INTEL_VENDOR)


def vendor_hints_or_all(detected_vendors: set[str]) -> set[str]:
    if detected_vendors:
        return set(detected_vendors)
    return set(GPU_VENDOR_TYPES)
