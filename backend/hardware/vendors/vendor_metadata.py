"""SoAI - Shared GPU vendor metadata [backend/hardware/vendors/vendor_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from hardware.gpu_inventory.identity import normalize_identity_name
from hardware.vendors.vendor_types import (
    AMD_VENDOR,
    INTEL_VENDOR,
    NVIDIA_VENDOR,
    UNKNOWN_VENDOR,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "LINUX_GPU_CONTROLLER_MARKERS",
    "darwin_gpu_vendor_matches",
    "detect_vendor_from_name",
    "gpu_feature_names_from_compute_drivers",
    "linux_gpu_vendor_matches",
    "normalize_vendor_value",
    "ready_vendors_from_compute_drivers",
    "resolve_driver_version",
    "resolve_driver_version_by_vendor_prefix",
    "vendor_aliases",
    "vendor_driver_keys",
    "vendor_priority",
    "windows_gpu_vendor_matches",
)

LINUX_GPU_CONTROLLER_MARKERS: tuple[str, ...] = (
    "vga compatible controller",
    "3d controller",
    "display controller",
)

_LINUX_VENDOR_KEYWORDS: tuple[tuple[str, str], ...] = (
    (NVIDIA_VENDOR, NVIDIA_VENDOR),
    ("advanced micro devices", AMD_VENDOR),
    ("[amd/ati]", AMD_VENDOR),
    ("intel corporation", INTEL_VENDOR),
)

_WINDOWS_VENDOR_KEYWORDS: tuple[tuple[str, str], ...] = (
    (NVIDIA_VENDOR, NVIDIA_VENDOR),
    (AMD_VENDOR, AMD_VENDOR),
    ("radeon", AMD_VENDOR),
    (INTEL_VENDOR, INTEL_VENDOR),
)

_DARWIN_VENDOR_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("vendor: nvidia", NVIDIA_VENDOR),
    ("vendor: amd", AMD_VENDOR),
    ("vendor: intel", INTEL_VENDOR),
)

_READY_DRIVER_VENDOR_ITEMS: tuple[tuple[str, str], ...] = (
    ("CUDA", NVIDIA_VENDOR),
    ("AMDGPU", AMD_VENDOR),
    ("Level Zero", INTEL_VENDOR),
)

_DRIVER_FEATURE_ITEMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("CUDA", ("cuda",)),
    ("AMDGPU", ("amdgpu",)),
    ("Level Zero", ("level_zero", "oneapi")),
)


def normalize_vendor_value(value: JSONValue) -> str:
    return value.strip().lower() if isinstance(value, str) and value.strip() else ""


def detect_vendor_from_name(name: str) -> str:
    matches = windows_gpu_vendor_matches(name)
    for vendor in (NVIDIA_VENDOR, AMD_VENDOR, INTEL_VENDOR):
        if vendor in matches:
            return vendor
    return UNKNOWN_VENDOR


def linux_gpu_vendor_matches(line: str) -> set[str]:
    line_lower = line.lower()
    if not any(marker in line_lower for marker in LINUX_GPU_CONTROLLER_MARKERS):
        return set()
    return _vendor_matches(line_lower, _LINUX_VENDOR_KEYWORDS)


def windows_gpu_vendor_matches(text: str) -> set[str]:
    return _vendor_matches(text.lower(), _WINDOWS_VENDOR_KEYWORDS)


def darwin_gpu_vendor_matches(text: str) -> set[str]:
    return _vendor_matches(text.lower(), _DARWIN_VENDOR_KEYWORDS)


def vendor_aliases(value: str) -> set[str]:
    normalized = normalize_identity_name(value)
    aliases = {normalized}
    if NVIDIA_VENDOR in normalized or normalized == "10de":
        aliases.add(NVIDIA_VENDOR)
    if (
        "advancedmicrodevices" in normalized
        or normalized == AMD_VENDOR
        or normalized in {"1002", "1022"}
    ):
        aliases.add(AMD_VENDOR)
    if INTEL_VENDOR in normalized or normalized == "8086":
        aliases.add(INTEL_VENDOR)
    return aliases


def vendor_driver_keys(vendor_type: str) -> tuple[str, ...]:
    normalized_vendor = vendor_type.lower()
    if normalized_vendor == NVIDIA_VENDOR:
        return (NVIDIA_VENDOR, "cuda")
    if normalized_vendor == AMD_VENDOR:
        return (AMD_VENDOR, "amdgpu")
    if normalized_vendor == INTEL_VENDOR:
        return (INTEL_VENDOR, "level zero")
    return (normalized_vendor,)


def resolve_driver_version(compute_drivers: JSONDict, vendor_type: str) -> str | None:
    vendor_keys = vendor_driver_keys(vendor_type)
    for driver_name, driver_value in compute_drivers.items():
        if not isinstance(driver_name, str) or not isinstance(driver_value, Mapping):
            continue
        normalized_driver_name = driver_name.lower()
        if not any(vendor_key in normalized_driver_name for vendor_key in vendor_keys):
            continue
        version_value = driver_value.get("driver_version") or driver_value.get("version")
        if isinstance(version_value, str) and version_value:
            return version_value
    return None


def resolve_driver_version_by_vendor_prefix(
    compute_drivers: JSONDict,
    vendor_type: str | None,
) -> str | None:
    vendor_prefix = vendor_type.lower() if isinstance(vendor_type, str) else ""
    for driver_name, driver_value in compute_drivers.items():
        if not isinstance(driver_value, Mapping):
            continue
        driver_name_text = driver_name.lower() if isinstance(driver_name, str) else ""
        if vendor_prefix and vendor_prefix not in driver_name_text:
            continue
        version_value = driver_value.get("driver_version") or driver_value.get("version")
        if isinstance(version_value, str) and version_value:
            return version_value
    return None


def ready_vendors_from_compute_drivers(compute_drivers: JSONDict) -> set[str]:
    ready_vendors: set[str] = set()
    for driver_name, vendor in _READY_DRIVER_VENDOR_ITEMS:
        if driver_name in compute_drivers:
            ready_vendors.add(vendor)
    return ready_vendors


def gpu_feature_names_from_compute_drivers(compute_drivers: JSONDict) -> set[str]:
    gpu_features: set[str] = set()
    for driver_name, feature_names in _DRIVER_FEATURE_ITEMS:
        if driver_name in compute_drivers:
            gpu_features.update(feature_names)
    return gpu_features


def vendor_priority(vendor: str) -> int:
    if vendor == NVIDIA_VENDOR:
        return 3
    if vendor == AMD_VENDOR:
        return 2
    if vendor == INTEL_VENDOR:
        return 1
    return 0


def _vendor_matches(text_lower: str, keyword_items: tuple[tuple[str, str], ...]) -> set[str]:
    vendors: set[str] = set()
    for keyword, vendor in keyword_items:
        if keyword in text_lower:
            vendors.add(vendor)
    return vendors
