"""SoAI - Windows GPU adapter payload parsing [backend/hardware/gpu_inventory/windows_adapters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.validation.strings import coerce_optional_trimmed_str
from hardware.gpu_inventory.display_adapters import (
    BASIC_DISPLAY_TYPE,
    VIRTUAL_DISPLAY_TYPE,
    classify_display_adapter,
)
from hardware.gpu_inventory.entries import build_gpu_entry
from hardware.gpu_inventory.identity import windows_adapter_primary_device_id
from hardware.gpu_inventory.memory_metrics import (
    bytes_to_mebibytes,
    coerce_nonnegative_memory_bytes,
)
from hardware.operations import create_device_id
from hardware.vendors.vendor_metadata import detect_vendor_from_name
from hardware.vendors.vendor_types import (
    AMD_VENDOR,
    INTEL_VENDOR,
    NVIDIA_VENDOR,
    UNKNOWN_VENDOR,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "WINDOWS_VIDEO_CONTROLLER_QUERY",
    "build_windows_gpu_entry",
    "classify_windows_display_adapter",
    "coerce_windows_gpu_name",
    "detect_windows_adapter_vendor",
    "detect_windows_gpu_vendor",
    "windows_adapter_pci_vendor_id",
)

WINDOWS_VIDEO_CONTROLLER_QUERY = (
    "Get-CimInstance -ClassName Win32_VideoController | "
    "Select-Object Name,AdapterRAM,DriverVersion,PNPDeviceID,DeviceID,"
    "AdapterCompatibility,VideoProcessor,InstalledDisplayDrivers,Status,"
    "ConfigManagerErrorCode | ConvertTo-Json -Compress"
)
_WINDOWS_PCI_VENDOR_PATTERN = r"(?:^|\\|&)VEN_([0-9A-Fa-f]{4})(?:&|$)"
_WINDOWS_PCI_DEVICE_PATTERN = r"(?:^|\\|&)DEV_([0-9A-Fa-f]{4})(?:&|$)"
_VIRTUAL_NAME_MARKERS: tuple[str, ...] = (
    "oculus",
    "rift",
    "meta quest",
    "virtual display",
    "virtual monitor",
    "indirect display",
    "idd",
    "mirror driver",
    "remote display",
    "spacedesk",
    "parsec",
    "steam streaming",
    "splashtop",
    "duet display",
    "dummy display",
)
_BASIC_NAME_MARKERS: tuple[str, ...] = (
    "microsoft basic display",
    "basic render",
    "basic display",
)
_NON_PCI_DEVICE_PREFIXES: tuple[str, ...] = (
    "DISPLAY\\",
    "ROOT\\DISPLAY",
    "ROOT\\BASICDISPLAY",
    "ROOT\\INDIRECTDISPLAY",
    "ROOT\\RDP",
    "SWD\\",
    "USB\\",
    "UMB\\",
)


def coerce_windows_gpu_name(value: JSONValue) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return "Unknown GPU"


def detect_windows_gpu_vendor(name: str) -> str:
    return detect_vendor_from_name(name)


def detect_windows_adapter_vendor(gpu_info: JSONDict, name: str) -> str:
    pci_vendor_id = windows_adapter_pci_vendor_id(gpu_info)
    if pci_vendor_id == "10de":
        return NVIDIA_VENDOR
    if pci_vendor_id in {"1002", "1022"}:
        return AMD_VENDOR
    if pci_vendor_id == "8086":
        return INTEL_VENDOR
    return detect_windows_gpu_vendor(name)


def windows_adapter_pci_vendor_id(gpu_info: JSONDict) -> str:
    return _first_pci_id(gpu_info, _WINDOWS_PCI_VENDOR_PATTERN)


def windows_adapter_pci_device_id(gpu_info: JSONDict) -> str:
    return _first_pci_id(gpu_info, _WINDOWS_PCI_DEVICE_PATTERN)


def classify_windows_display_adapter(
    *,
    gpu_info: JSONDict,
    vendor: str,
    name: str,
) -> str | None:
    pci_vendor_id = windows_adapter_pci_vendor_id(gpu_info)
    if _is_real_compute_pci_vendor(pci_vendor_id):
        return None
    pnp_device_id = _adapter_identifier_text(gpu_info).upper()
    normalized_name = name.strip().lower()
    if any(marker in normalized_name for marker in _BASIC_NAME_MARKERS):
        return BASIC_DISPLAY_TYPE
    if any(marker in normalized_name for marker in _VIRTUAL_NAME_MARKERS):
        return VIRTUAL_DISPLAY_TYPE
    if any(pnp_device_id.startswith(prefix) for prefix in _NON_PCI_DEVICE_PREFIXES):
        return VIRTUAL_DISPLAY_TYPE
    classified = classify_display_adapter(UNKNOWN_VENDOR, pci_vendor_id, None)
    if classified is not None:
        return classified
    if vendor == UNKNOWN_VENDOR and not pnp_device_id.startswith("PCI\\"):
        return VIRTUAL_DISPLAY_TYPE
    return None


def build_windows_gpu_entry(
    *,
    gpu_info: JSONDict,
    gpu_index: int,
    vendor: str,
    vendor_id: JSONValue,
    name: str,
    compute_capable: bool = True,
    display_adapter_type: str | None = None,
) -> JSONDict:
    primary_device_id = windows_adapter_primary_device_id(gpu_info, vendor)
    if not primary_device_id:
        raise StateError(
            f"Windows GPU identifier is required for device identity (index {gpu_index}).",
        )
    total_memory_bytes = coerce_nonnegative_memory_bytes(gpu_info.get("AdapterRAM"))
    entry = build_gpu_entry(
        vendor=vendor,
        index=gpu_index,
        vendor_id=vendor_id,
        device_id=create_device_id("gpu", primary_device_id),
        name=name,
        memory_used_mb=0,
        memory_total_mb=bytes_to_mebibytes(total_memory_bytes),
        percent_used=0.0,
    )
    entry.update(
        {
            "compute_capable": compute_capable,
            "display_adapter_type": display_adapter_type,
            "telemetry_available": compute_capable,
            "telemetry_unavailable_reason": None if compute_capable else "display_adapter",
        },
    )
    pci_vendor_id = windows_adapter_pci_vendor_id(gpu_info)
    pci_device_id = windows_adapter_pci_device_id(gpu_info)
    if pci_vendor_id:
        entry["pci_vendor_id"] = pci_vendor_id
    if pci_device_id:
        entry["pci_device_id"] = pci_device_id
    return entry


def _adapter_identifier_text(gpu_info: JSONDict) -> str:
    for key in ("PNPDeviceID", "DeviceID"):
        normalized = coerce_optional_trimmed_str(gpu_info.get(key))
        if normalized is not None:
            return normalized
    return ""


def _first_pci_id(gpu_info: JSONDict, pattern: str) -> str:
    identifier = _adapter_identifier_text(gpu_info)
    match = re.search(pattern, identifier)
    return match.group(1).lower() if match is not None else ""


def _is_real_compute_pci_vendor(pci_vendor_id: str) -> bool:
    return pci_vendor_id in {"10de", "1002", "1022", "8086"}
