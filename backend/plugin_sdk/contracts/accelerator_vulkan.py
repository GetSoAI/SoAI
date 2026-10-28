"""SoAI - Plugin SDK Vulkan accelerator binding [backend/plugin_sdk/contracts/accelerator_vulkan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ConfigurationError, ValidationError
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingState,
    compare_gpu_physical_identities,
)
from core.hardware.gpu_physical_observations import read_gpu_physical_identity
from core.types.json import JSONDict, is_json_dict
from core.validation.numbers import coerce_int_from_json
from plugin_sdk.contracts.accelerator_device_identity import (
    accelerator_field_value,
    normalize_accelerator_hex_id,
)
from plugin_sdk.contracts.accelerator_vulkan_acquisition import VulkanDeviceAcquisition
from plugin_sdk.contracts.accelerator_vulkan_devices import (
    VulkanBindingFailure,
    VulkanPhysicalDevice,
    hex_identity_pair,
    vulkan_binding_error,
)

__all__ = ("resolve_vulkan_visible_devices",)


def resolve_vulkan_visible_devices(gpus: list[JSONDict]) -> list[str]:
    embedded_indices = _embedded_vulkan_indices(gpus)
    if len(embedded_indices) == len(gpus):
        return embedded_indices
    acquisition = VulkanDeviceAcquisition()
    unresolved: ConfigurationError | None = None
    for vulkan_devices in acquisition.rosters():
        if not vulkan_devices:
            raise vulkan_binding_error(VulkanBindingFailure.DEVICE_UNAVAILABLE)
        visible_devices: list[str] = []
        for gpu in gpus:
            device = _match_vulkan_device(gpu, vulkan_devices)
            if device is None:
                unresolved = vulkan_binding_error(
                    VulkanBindingFailure.IDENTITY_UNAVAILABLE, label=_gpu_label(gpu)
                )
                break
            visible_devices.append(str(device.index))
        else:
            return visible_devices
    raise acquisition.failure(unresolved)


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


def _gpu_label(gpu: JSONDict) -> str:
    device_id = gpu.get("device_id")
    return device_id if isinstance(device_id, str) and device_id else str(gpu.get("name") or "GPU")


def _match_vulkan_device(
    gpu: JSONDict,
    devices: list[VulkanPhysicalDevice],
) -> VulkanPhysicalDevice | None:
    label = _gpu_label(gpu)
    try:
        selected_identity = read_gpu_physical_identity(gpu)
    except ValidationError as exception:
        raise vulkan_binding_error(VulkanBindingFailure.IDENTITY_CONFLICT, label=label) from (
            exception
        )
    if selected_identity is None:
        raise vulkan_binding_error(VulkanBindingFailure.IDENTITY_UNAVAILABLE, label=label)
    selected_vendor_device = _gpu_vendor_device_key(gpu)
    matches: list[VulkanPhysicalDevice] = []
    incomparable = False
    for device in devices:
        device_identity = device.physical_identity()
        relation = (
            GPUPhysicalBindingState.IDENTITY_UNAVAILABLE
            if device_identity is None
            else compare_gpu_physical_identities(selected_identity, device_identity)
        )
        device_vendor_device = device.vendor_device_key()
        if (
            relation == GPUPhysicalBindingState.BOUND
            and selected_vendor_device is not None
            and device_vendor_device is not None
            and device_vendor_device != selected_vendor_device
        ):
            relation = GPUPhysicalBindingState.IDENTITY_CONFLICT
        if relation == GPUPhysicalBindingState.IDENTITY_CONFLICT:
            raise vulkan_binding_error(VulkanBindingFailure.IDENTITY_CONFLICT, label=label)
        if relation == GPUPhysicalBindingState.IDENTITY_UNAVAILABLE:
            incomparable = True
        elif relation == GPUPhysicalBindingState.BOUND:
            matches.append(device)
    distinct_matches = _distinct_vulkan_observations(matches)
    if len(distinct_matches) > 1:
        raise vulkan_binding_error(
            VulkanBindingFailure.DEVICE_AMBIGUOUS,
            label=label,
            indices=tuple(device.index for device in distinct_matches),
        )
    if distinct_matches:
        return distinct_matches[0]
    if incomparable:
        return None
    raise vulkan_binding_error(VulkanBindingFailure.DEVICE_UNAVAILABLE, label=label)


def _distinct_vulkan_observations(
    devices: list[VulkanPhysicalDevice],
) -> list[VulkanPhysicalDevice]:
    distinct: list[VulkanPhysicalDevice] = []
    for device in sorted(devices, key=lambda observation: observation.index):
        if not any(
            device.driver_identity
            and _vulkan_observation_key(device) == _vulkan_observation_key(retained)
            for retained in distinct
        ):
            distinct.append(device)
    return distinct


def _vulkan_observation_key(
    device: VulkanPhysicalDevice,
) -> tuple[str | None, str | None, str | None, str | None, str | None, tuple[str, ...]]:
    return (
        device.uuid,
        device.pci_bdf_full,
        device.vendor_id,
        device.device_id,
        device.name_key,
        device.driver_identity,
    )


def _gpu_vendor_device_key(gpu: JSONDict) -> tuple[int, int] | None:
    return hex_identity_pair(
        normalize_accelerator_hex_id(accelerator_field_value(gpu, ("pci_vendor_id",))),
        normalize_accelerator_hex_id(accelerator_field_value(gpu, ("pci_device_id",))),
    )
