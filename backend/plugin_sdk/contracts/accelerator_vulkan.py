"""SoAI - Plugin SDK Vulkan accelerator binding [backend/plugin_sdk/contracts/accelerator_vulkan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ConfigurationError
from core.types.json import JSONDict, is_json_dict
from core.validation.numbers import coerce_int_from_json
from plugin_sdk.contracts.accelerator_device_identity import (
    accelerator_field_value,
    accelerator_string_field,
    normalize_accelerator_hex_id,
    normalize_accelerator_identity,
    optional_accelerator_pci_bdf,
)
from plugin_sdk.contracts.accelerator_vulkan_devices import (
    VulkanPhysicalDevice,
    query_vulkan_devices,
)

__all__ = ("resolve_vulkan_visible_devices",)


def resolve_vulkan_visible_devices(gpus: list[JSONDict]) -> list[str]:
    embedded_indices = _embedded_vulkan_indices(gpus)
    if len(embedded_indices) == len(gpus):
        return embedded_indices
    vulkan_devices = query_vulkan_devices()
    if not vulkan_devices:
        raise ConfigurationError(
            "Selected GPU binding requires Vulkan device mapping, but vulkaninfo did not return physical devices.",
        )
    visible_devices: list[str] = []
    for gpu in gpus:
        visible_devices.append(str(_match_vulkan_device(gpu, vulkan_devices).index))
    return visible_devices


def _embedded_vulkan_indices(gpus: list[JSONDict]) -> list[str]:
    indices: list[str] = []
    for gpu in gpus:
        binding_value = gpu.get("binding")
        binding = binding_value if is_json_dict(binding_value) else {}
        raw_index = binding.get("vulkan_index") if binding else gpu.get("vulkan_index")
        index = coerce_int_from_json(raw_index, default=None, allow_bool=False)
        if index is None or index < 0:
            return []
        indices.append(str(index))
    return indices


def _match_vulkan_device(
    gpu: JSONDict,
    devices: list[VulkanPhysicalDevice],
) -> VulkanPhysicalDevice:
    pci_bdf = optional_accelerator_pci_bdf(
        accelerator_string_field(gpu, ("pci_bdf", "pci_bdf_full")),
    )
    if pci_bdf is not None:
        pci_matches = [device for device in devices if device.pci_bdf == pci_bdf]
        if len(pci_matches) == 1:
            return pci_matches[0]
    vendor_device_key = _gpu_vendor_device_key(gpu)
    if vendor_device_key is not None:
        vendor_device_matches = [
            device for device in devices if _vulkan_vendor_device_key(device) == vendor_device_key
        ]
        if len(vendor_device_matches) == 1:
            return vendor_device_matches[0]
    match_key = _gpu_match_key(gpu)
    if match_key is not None:
        key_matches = [device for device in devices if _vulkan_match_key(device) == match_key]
        if len(key_matches) == 1:
            return key_matches[0]
    device_id = gpu.get("device_id")
    label = device_id if isinstance(device_id, str) and device_id else str(gpu.get("name") or "GPU")
    raise ConfigurationError(
        f"Selected GPU '{label}' cannot be mapped to a unique Vulkan physical device.",
    )


def _gpu_match_key(gpu: JSONDict) -> tuple[str | None, str | None, str | None] | None:
    name_key = normalize_accelerator_identity(accelerator_string_field(gpu, ("name",)))
    vendor_id = normalize_accelerator_hex_id(accelerator_field_value(gpu, ("pci_vendor_id",)))
    device_id = normalize_accelerator_hex_id(accelerator_field_value(gpu, ("pci_device_id",)))
    if name_key is None and vendor_id is None and device_id is None:
        return None
    return (vendor_id, device_id, name_key)


def _gpu_vendor_device_key(gpu: JSONDict) -> tuple[str, str] | None:
    vendor_id = normalize_accelerator_hex_id(accelerator_field_value(gpu, ("pci_vendor_id",)))
    device_id = normalize_accelerator_hex_id(accelerator_field_value(gpu, ("pci_device_id",)))
    if vendor_id is None or device_id is None:
        return None
    return (vendor_id, device_id)


def _vulkan_match_key(
    device: VulkanPhysicalDevice,
) -> tuple[str | None, str | None, str | None]:
    return (device.vendor_id, device.device_id, device.name_key)


def _vulkan_vendor_device_key(device: VulkanPhysicalDevice) -> tuple[str, str] | None:
    if device.vendor_id is None or device.device_id is None:
        return None
    return (device.vendor_id, device.device_id)
