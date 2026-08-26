"""SoAI - Vulkan physical device discovery [backend/plugin_sdk/contracts/accelerator_vulkan_devices.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_value
from core.system.commands import run_argv_capture
from core.types.json import JSONDict, JSONValue, is_json_dict
from core.validation.numbers import coerce_int_from_json
from plugin_sdk.contracts.accelerator_device_identity import (
    accelerator_field_value,
    accelerator_string_field,
    normalize_accelerator_hex_id,
    normalize_accelerator_identity,
    optional_accelerator_pci_bdf,
)

__all__ = (
    "VulkanPhysicalDevice",
    "query_vulkan_devices",
)


@dataclass(frozen=True, slots=True)
class VulkanPhysicalDevice:
    index: int
    pci_bdf: str | None
    name_key: str | None
    vendor_id: str | None
    device_id: str | None


def query_vulkan_devices() -> list[VulkanPhysicalDevice]:
    for command in (["vulkaninfo", "--summary", "--json"], ["vulkaninfo", "--json"]):
        result = run_argv_capture(command, timeout=8)
        if result.return_code != 0 or not result.stdout.strip():
            continue
        try:
            payload = parse_json_value(result.stdout)
        except (ValidationError, TypeError):
            continue
        devices = _parse_vulkan_devices(payload)
        if devices:
            return devices
    for command in (["vulkaninfo", "--summary"], ["vulkaninfo"]):
        result = run_argv_capture(command, timeout=8)
        if result.return_code != 0 or not result.stdout.strip():
            continue
        devices = _parse_vulkan_summary_devices(result.stdout)
        if devices:
            return devices
    return []


def _parse_vulkan_devices(payload: JSONValue) -> list[VulkanPhysicalDevice]:
    devices: list[VulkanPhysicalDevice] = []
    for index, device_payload in enumerate(_find_device_payloads(payload, depth=0)):
        parsed = _parse_vulkan_device(device_payload, index)
        if parsed is not None:
            devices.append(parsed)
    return devices


def _find_device_payloads(value: JSONValue, *, depth: int) -> list[JSONDict]:
    if depth > 4:
        return []
    if isinstance(value, list):
        dict_items = [item for item in value if is_json_dict(item)]
        if dict_items and any(_has_vulkan_device_shape(item) for item in dict_items):
            return [dict(item) for item in dict_items]
        nested_items: list[JSONDict] = []
        for item in value:
            nested_items.extend(_find_device_payloads(item, depth=depth + 1))
        return nested_items
    if not is_json_dict(value):
        return []
    direct_items: list[JSONDict] = []
    for key, item in value.items():
        lowered = key.lower().replace(" ", "").replace("_", "")
        if lowered in {"devices", "physicaldevices", "vulkanphysicaldevices"}:
            direct_items.extend(_find_device_payloads(item, depth=depth + 1))
    if direct_items:
        return direct_items
    nested_device_items: list[JSONDict] = []
    for item in value.values():
        nested_device_items.extend(_find_device_payloads(item, depth=depth + 1))
    return nested_device_items


def _has_vulkan_device_shape(value: JSONDict) -> bool:
    if _device_properties(value):
        return True
    return any(key in value for key in ("deviceName", "device_name", "vendorID", "deviceID"))


def _parse_vulkan_device(payload: JSONDict, index: int) -> VulkanPhysicalDevice | None:
    properties = _device_properties(payload)
    source = properties if properties else payload
    if _is_cpu_device_type(accelerator_field_value(source, ("deviceType", "device_type", "type"))):
        return None
    name_key = normalize_accelerator_identity(
        accelerator_string_field(source, ("deviceName", "device_name", "name")),
    )
    vendor_id = normalize_accelerator_hex_id(
        accelerator_field_value(source, ("vendorID", "vendor_id", "vendorId")),
    )
    device_id = normalize_accelerator_hex_id(
        accelerator_field_value(source, ("deviceID", "device_id", "deviceId")),
    )
    pci_bdf = _extract_pci_bdf(payload)
    if name_key is None and vendor_id is None and device_id is None and pci_bdf is None:
        return None
    return VulkanPhysicalDevice(
        index=index,
        pci_bdf=pci_bdf,
        name_key=name_key,
        vendor_id=vendor_id,
        device_id=device_id,
    )


def _is_cpu_device_type(value: JSONValue) -> bool:
    if isinstance(value, str):
        normalized = value.strip().upper()
        return normalized == "PHYSICAL_DEVICE_TYPE_CPU" or normalized.endswith("_CPU")
    numeric_value = coerce_int_from_json(value, default=None, allow_bool=False)
    return numeric_value == 4


def _parse_vulkan_summary_devices(output: str) -> list[VulkanPhysicalDevice]:
    devices: list[VulkanPhysicalDevice] = []
    current_index: int | None = None
    current_fields: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        parsed_index = _summary_gpu_header_index(line)
        if parsed_index is not None:
            _append_summary_device(devices, current_index, current_fields)
            current_index = parsed_index
            current_fields = {}
            continue
        if current_index is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        current_fields[key.strip()] = value.strip()
    _append_summary_device(devices, current_index, current_fields)
    return devices


def _summary_gpu_header_index(line: str) -> int | None:
    if not (line.startswith("GPU") and line.endswith(":")):
        return None
    raw_index = line[3:-1]
    return int(raw_index) if raw_index.isdigit() else None


def _append_summary_device(
    devices: list[VulkanPhysicalDevice],
    index: int | None,
    fields: dict[str, str],
) -> None:
    if index is None:
        return
    device_type = fields.get("deviceType", "").strip().upper()
    if device_type == "PHYSICAL_DEVICE_TYPE_CPU":
        return
    name_key = normalize_accelerator_identity(fields.get("deviceName"))
    vendor_id = normalize_accelerator_hex_id(fields.get("vendorID"))
    device_id = normalize_accelerator_hex_id(fields.get("deviceID"))
    if name_key is None and vendor_id is None and device_id is None:
        return
    devices.append(
        VulkanPhysicalDevice(
            index=index,
            pci_bdf=None,
            name_key=name_key,
            vendor_id=vendor_id,
            device_id=device_id,
        ),
    )


def _device_properties(payload: JSONDict) -> JSONDict | None:
    for key in ("VkPhysicalDeviceProperties", "deviceProperties", "properties"):
        value = payload.get(key)
        if is_json_dict(value):
            return dict(value)
    return None


def _extract_pci_bdf(payload: JSONDict) -> str | None:
    pci_payload = _find_pci_payload(payload, depth=0)
    if pci_payload is None:
        return None
    domain = coerce_int_from_json(
        accelerator_field_value(pci_payload, ("pciDomain", "domain")),
        default=0,
    )
    bus = coerce_int_from_json(
        accelerator_field_value(pci_payload, ("pciBus", "bus")),
        default=None,
    )
    device = coerce_int_from_json(
        accelerator_field_value(pci_payload, ("pciDevice", "device", "slot")),
        default=None,
    )
    function = coerce_int_from_json(
        accelerator_field_value(pci_payload, ("pciFunction", "function")),
        default=0,
    )
    if bus is None or device is None or function is None or domain is None:
        return optional_accelerator_pci_bdf(
            accelerator_string_field(pci_payload, ("pciBusID", "pci_bdf", "bdf")),
        )
    return optional_accelerator_pci_bdf(f"{domain:04x}:{bus:02x}:{device:02x}.{function}")


def _find_pci_payload(value: JSONValue, *, depth: int) -> JSONDict | None:
    if depth > 5 or not is_json_dict(value):
        return None
    for key, item in value.items():
        lowered = key.lower()
        if "pci" in lowered and is_json_dict(item):
            return dict(item)
    for item in value.values():
        if is_json_dict(item):
            nested = _find_pci_payload(item, depth=depth + 1)
            if nested is not None:
                return nested
        elif isinstance(item, list):
            for list_item in item:
                nested = _find_pci_payload(list_item, depth=depth + 1)
                if nested is not None:
                    return nested
    return None
