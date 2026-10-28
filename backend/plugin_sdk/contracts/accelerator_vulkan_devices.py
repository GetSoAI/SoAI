"""SoAI - Vulkan physical device discovery [backend/plugin_sdk/contracts/accelerator_vulkan_devices.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from core.errors.exceptions import ConfigurationError
from core.hardware.gpu_physical_identity import GPUPhysicalIdentity, vulkan_device_uuid_identity
from core.types.json import JSONValue
from plugin_sdk.contracts.accelerator_device_identity import (
    normalize_accelerator_hex_id,
    normalize_accelerator_identity,
)

__all__ = (
    "VULKAN_ACQUISITION_TIMEOUT_SECONDS",
    "VulkanBindingFailure",
    "VulkanPhysicalDevice",
    "hex_identity_pair",
    "parse_vulkan_text_devices",
    "vulkan_binding_error",
)

VULKAN_ACQUISITION_TIMEOUT_SECONDS = 15
_GPU_HEADER_PATTERN = r"GPU(\d+):"
_FIELD_PATTERN = r"(?P<indent>[ \t]+)(?P<key>[A-Za-z][A-Za-z0-9]*)[ \t]*=[ \t]*(?P<value>.*)"
_PROPERTY_BLOCK_PATTERN = r"VkPhysicalDevice(?P<block>[A-Za-z0-9]*?)Properties(?P<suffix>KHR|EXT)?"
_SUMMARY_FIELDS = (
    "apiVersion",
    "deviceID",
    "deviceName",
    "deviceType",
    "deviceUUID",
    "driverID",
    "driverInfo",
    "driverName",
    "driverUUID",
    "driverVersion",
    "vendorID",
)
_UUID_FIELDS = ("deviceUUID", "driverUUID")
_DRIVER_BLOCK_FIELDS = ("driverID", "driverInfo", "driverName")
_PROPERTY_BLOCK_FIELDS = (
    (
        ("", ""),
        ("apiVersion", "deviceID", "deviceName", "deviceType", "driverVersion", "vendorID"),
    ),
    (("PCIBusInfo", "EXT"), ("pciBus", "pciDevice", "pciDomain", "pciFunction")),
    (("Vulkan11", ""), _UUID_FIELDS),
    (("ID", ""), _UUID_FIELDS),
    (("ID", "KHR"), _UUID_FIELDS),
    (("Vulkan12", ""), _DRIVER_BLOCK_FIELDS),
    (("Driver", ""), _DRIVER_BLOCK_FIELDS),
    (("Driver", "KHR"), _DRIVER_BLOCK_FIELDS),
)
_DRIVER_FIELDS = (
    "apiVersion",
    "driverID",
    "driverInfo",
    "driverName",
    "driverUUID",
    "driverVersion",
)
_VERSION_FIELDS = frozenset(("apiVersion", "driverVersion"))
_PCI_FIELDS = ("pciDomain", "pciBus", "pciDevice", "pciFunction")


class VulkanBindingFailure(StrEnum):
    RUNTIME_UNAVAILABLE = "vulkan_runtime_unavailable"
    QUERY_TIMEOUT = "vulkan_query_timeout"
    FORMAT_UNSUPPORTED = "vulkan_format_unsupported"
    DEVICE_UNAVAILABLE = "vulkan_device_unavailable"
    IDENTITY_UNAVAILABLE = "vulkan_identity_unavailable"
    IDENTITY_CONFLICT = "vulkan_identity_conflict"
    DEVICE_AMBIGUOUS = "vulkan_device_ambiguous"


@dataclass(frozen=True, slots=True)
class VulkanPhysicalDevice:
    index: int
    name_key: str | None
    vendor_id: str | None
    device_id: str | None
    uuid: str | None = None
    pci_bdf_full: str | None = None
    driver_identity: tuple[str, ...] = ()

    def physical_identity(self) -> GPUPhysicalIdentity | None:
        if self.uuid is None and self.pci_bdf_full is None:
            return None
        return GPUPhysicalIdentity(uuid=self.uuid, pci_bdf_full=self.pci_bdf_full)

    def vendor_device_key(self) -> tuple[int, int] | None:
        return hex_identity_pair(self.vendor_id, self.device_id)


def hex_identity_pair(vendor_id: str | None, device_id: str | None) -> tuple[int, int] | None:
    if vendor_id is None or device_id is None:
        return None
    return (int(vendor_id, 16), int(device_id, 16))


def vulkan_binding_error(
    failure: VulkanBindingFailure,
    *,
    label: str | None = None,
    indices: tuple[int, ...] = (),
) -> ConfigurationError:
    details: dict[str, JSONValue] = {"reason": failure.value}
    if label is not None:
        details["device_id"] = label
    if indices:
        details["vulkan_indices"] = list(indices)
    return ConfigurationError(
        _failure_message(failure, label or "GPU", ", ".join(str(index) for index in indices)),
        details=details,
    )


def _failure_message(failure: VulkanBindingFailure, label: str, indices: str) -> str:
    match failure:
        case VulkanBindingFailure.RUNTIME_UNAVAILABLE:
            return (
                "Selected GPU binding requires Vulkan device mapping, but vulkaninfo is unavailable "
                "or failed. Install the distribution Vulkan tools and driver, or bind all GPUs."
            )
        case VulkanBindingFailure.QUERY_TIMEOUT:
            return (
                "Selected GPU binding requires Vulkan device mapping, but vulkaninfo did not finish "
                f"within {VULKAN_ACQUISITION_TIMEOUT_SECONDS} seconds. Check the Vulkan driver, or "
                "bind all GPUs."
            )
        case VulkanBindingFailure.FORMAT_UNSUPPORTED:
            return (
                "Selected GPU binding requires Vulkan device mapping, but vulkaninfo produced output "
                "in an unsupported format. Update the distribution Vulkan tools, or bind all GPUs."
            )
        case VulkanBindingFailure.DEVICE_UNAVAILABLE:
            return (
                f"Selected GPU '{label}' is not present among the Vulkan physical devices. Check "
                "the Vulkan driver for this GPU, or select a different GPU."
            )
        case VulkanBindingFailure.IDENTITY_UNAVAILABLE:
            return (
                f"Selected GPU '{label}' has no UUID or PCI identity shared with the Vulkan "
                "physical devices, so it cannot be bound safely. Bind all GPUs instead."
            )
        case VulkanBindingFailure.IDENTITY_CONFLICT:
            return (
                f"Selected GPU '{label}' has conflicting UUID, PCI or device identity in the Vulkan "
                "physical device observations, so it cannot be bound safely."
            )
        case VulkanBindingFailure.DEVICE_AMBIGUOUS:
            return (
                f"Selected GPU '{label}' is exposed by several distinct Vulkan drivers (devices "
                f"{indices}). Remove the duplicate Vulkan driver (ICD), or bind all GPUs."
            )


def parse_vulkan_text_devices(output: str) -> list[VulkanPhysicalDevice] | None:
    sections: dict[int, dict[str, str]] = {}
    current_fields: dict[str, str] | None = None
    current_block: str | None = None
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        header = re.fullmatch(_GPU_HEADER_PATTERN, line)
        if header is not None:
            index = int(header.group(1))
            if index in sections:
                return None
            current_fields = {}
            sections[index] = current_fields
            current_block = None
            continue
        if current_fields is None or not line:
            continue
        if not line[0].isspace():
            if line.endswith(":"):
                current_block = line[:-1]
            continue
        field = re.fullmatch(_FIELD_PATTERN, line)
        if field is None:
            continue
        key, value = field.group("key"), field.group("value").strip()
        if key not in _accepted_fields(current_block, field.group("indent")):
            continue
        if current_fields.get(key, value) != value:
            return None
        current_fields[key] = value
    if not sections:
        return None
    devices: list[VulkanPhysicalDevice] = []
    for index, fields in sorted(sections.items()):
        device_type = fields.get("deviceType", "").split()
        if not device_type:
            return None
        if device_type[0] == "PHYSICAL_DEVICE_TYPE_CPU":
            continue
        device = _vulkan_device_from_fields(index, fields)
        if device is None:
            return None
        devices.append(device)
    return devices


def _accepted_fields(block: str | None, indent: str) -> tuple[str, ...]:
    if block is None:
        return _SUMMARY_FIELDS
    properties = re.fullmatch(_PROPERTY_BLOCK_PATTERN, block)
    if indent != "\t" or properties is None:
        return ()
    observed_block = (properties.group("block"), properties.group("suffix") or "")
    for property_block, fields in _PROPERTY_BLOCK_FIELDS:
        if property_block == observed_block:
            return fields
    return ()


def _vulkan_device_from_fields(index: int, fields: dict[str, str]) -> VulkanPhysicalDevice | None:
    vendor_id = normalize_accelerator_hex_id(fields.get("vendorID"))
    device_uuid: str | None = None
    if "deviceUUID" in fields:
        if vendor_id is None:
            return None
        try:
            device_uuid = vulkan_device_uuid_identity(
                int(vendor_id, 16), UUID(fields["deviceUUID"])
            )
        except ValueError:
            return None
    pci_values = [fields.get(key) for key in _PCI_FIELDS]
    pci_bdf_full: str | None = None
    if any(value is not None for value in pci_values):
        if not all(value is not None and value.isdigit() for value in pci_values):
            return None
        domain, bus, device, function = (int(value) for value in pci_values if value is not None)
        if domain > 0xFFFFFFFF or bus > 0xFF or device > 0x1F or function > 0x7:
            return None
        pci_bdf_full = f"{domain:08x}:{bus:02x}:{device:02x}.{function}"
    return VulkanPhysicalDevice(
        index=index,
        name_key=normalize_accelerator_identity(fields.get("deviceName")),
        vendor_id=vendor_id,
        device_id=normalize_accelerator_hex_id(fields.get("deviceID")),
        uuid=device_uuid,
        pci_bdf_full=pci_bdf_full,
        driver_identity=_vulkan_driver_identity(fields),
    )


def _vulkan_driver_identity(fields: dict[str, str]) -> tuple[str, ...]:
    identity: list[str] = []
    for key in _DRIVER_FIELDS:
        value = fields.get(key)
        if value:
            identity.append(f"{key}={value.split()[0] if key in _VERSION_FIELDS else value}")
    return tuple(identity)
