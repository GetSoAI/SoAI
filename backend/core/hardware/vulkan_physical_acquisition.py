"""SoAI - Owned Vulkan physical device enumeration [backend/core/hardware/vulkan_physical_acquisition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import platform
from uuid import UUID

from core.concurrency.deadlines import deadline_after
from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import vulkan_device_uuid_identity
from core.hardware.vulkan_abi import (
    VulkanApplicationInfo,
    VulkanExtension,
    VulkanIdentityProperties,
    VulkanInstanceCreateInfo,
    VulkanPciProperties,
    VulkanProperties,
    VulkanProperties2,
)
from core.hardware.windows_adapter_address import read_windows_adapter_address
from core.types.json import JSONDict

__all__ = (
    "VULKAN_CPU_DEVICE_TYPE",
    "acquire_vulkan_physical_devices",
    "load_vulkan_library",
)

VULKAN_CPU_DEVICE_TYPE = 4


def acquire_vulkan_physical_devices(
    library: ctypes.CDLL, adapter_library: ctypes.CDLL | None = None
) -> tuple[JSONDict, ...]:
    library.vkCreateInstance.argtypes = [
        ctypes.POINTER(VulkanInstanceCreateInfo),
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    library.vkCreateInstance.restype = ctypes.c_int32
    library.vkDestroyInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    library.vkDestroyInstance.restype = None
    library.vkEnumeratePhysicalDevices.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    library.vkEnumeratePhysicalDevices.restype = ctypes.c_int32
    library.vkGetPhysicalDeviceProperties.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(VulkanProperties),
    ]
    library.vkGetPhysicalDeviceProperties.restype = None
    library.vkEnumerateDeviceExtensionProperties.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(VulkanExtension),
    ]
    library.vkEnumerateDeviceExtensionProperties.restype = ctypes.c_int32
    library.vkGetPhysicalDeviceProperties2.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(VulkanProperties2),
    ]
    library.vkGetPhysicalDeviceProperties2.restype = None
    deadline = deadline_after(5.0)
    application = VulkanApplicationInfo(
        structure_type=0, application_name=b"SoAI", api_version=(1 << 22) | (1 << 12)
    )
    create_info = VulkanInstanceCreateInfo(
        structure_type=1, application=ctypes.pointer(application)
    )
    instance = ctypes.c_void_p()
    status = library.vkCreateInstance(ctypes.byref(create_info), None, ctypes.byref(instance))
    if status != 0 or instance.value is None:
        raise StateError(
            "Vulkan instance creation is unavailable.", details={"native_status": status}
        )
    try:
        count = ctypes.c_uint32()
        status = library.vkEnumeratePhysicalDevices(instance, ctypes.byref(count), None)
        if status != 0 or count.value > 128:
            raise StateError("Vulkan physical enumeration count is unavailable.")
        devices = (ctypes.c_void_p * count.value)()
        expected_count = count.value
        status = library.vkEnumeratePhysicalDevices(instance, ctypes.byref(count), devices)
        if status != 0 or count.value != expected_count:
            raise StateError("Vulkan physical device count changed during acquisition.")
        observed: list[JSONDict] = []
        for vulkan_index, device in enumerate(devices):
            if deadline.expired():
                raise TimeoutError("Vulkan physical acquisition deadline expired.")
            if device is None:
                raise ValidationError("Vulkan physical device handle is missing.")
            properties = VulkanProperties()
            library.vkGetPhysicalDeviceProperties(device, ctypes.byref(properties))
            if properties.device_type not in (0, 1, 2, 3, 4):
                raise ValidationError("Vulkan physical device type is invalid.")
            if properties.device_type == VULKAN_CPU_DEVICE_TYPE:
                continue
            extension_count = ctypes.c_uint32()
            status = library.vkEnumerateDeviceExtensionProperties(
                device, None, ctypes.byref(extension_count), None
            )
            if status != 0 or extension_count.value > 4096:
                raise StateError("Vulkan device extensions are unavailable.")
            extensions = (VulkanExtension * extension_count.value)()
            expected_extensions = extension_count.value
            status = library.vkEnumerateDeviceExtensionProperties(
                device, None, ctypes.byref(extension_count), extensions
            )
            if status != 0 or expected_extensions != extension_count.value:
                raise StateError("Vulkan device extension roster changed.")
            pci_available = any(
                extension.name == b"VK_EXT_pci_bus_info" for extension in extensions
            )
            pci = VulkanPciProperties(structure_type=1000212000)
            identity = VulkanIdentityProperties(
                structure_type=1000071004, next=ctypes.addressof(pci) if pci_available else None
            )
            identity_available = properties.api_version >= ((1 << 22) | (1 << 12))
            extended = VulkanProperties2(
                structure_type=1000059001,
                next=(
                    ctypes.addressof(identity)
                    if identity_available
                    else (ctypes.addressof(pci) if pci_available else None)
                ),
            )
            library.vkGetPhysicalDeviceProperties2(device, ctypes.byref(extended))
            if (
                extended.properties.vendor_id,
                extended.properties.device_id,
                extended.properties.device_type,
            ) != (properties.vendor_id, properties.device_id, properties.device_type):
                raise ValidationError("Vulkan physical properties changed during acquisition.")
            vendor = {0x10DE: "nvidia", 0x1002: "amd", 0x8086: "intel"}.get(
                properties.vendor_id, "unknown"
            )
            candidate: JSONDict = {
                "vulkan_index": vulkan_index,
                "type": vendor,
                "vulkan_device_type": properties.device_type,
                "pci_vendor_id": f"{properties.vendor_id:04x}",
                "pci_device_id": f"{properties.device_id:04x}",
            }
            if identity_available and identity.device_luid_valid not in (0, 1):
                raise ValidationError("Vulkan device LUID validity is malformed.")
            if pci_available:
                pci_bdf_full = _pci_bdf_full(pci.domain, (pci.bus, pci.device, pci.function))
                if pci_bdf_full is None:
                    raise ValidationError("Vulkan native PCI locator is malformed.")
                candidate["pci_bdf_full"] = pci_bdf_full
            elif adapter_library is not None and identity_available and identity.device_luid_valid:
                adapter_address = read_windows_adapter_address(
                    adapter_library, bytes(identity.device_luid)
                )
                pci_bdf_full = (
                    _pci_bdf_full(0, adapter_address) if adapter_address is not None else None
                )
                if pci_bdf_full is not None:
                    candidate["pci_bdf_full"] = pci_bdf_full
            device_uuid = (
                vulkan_device_uuid_identity(
                    properties.vendor_id, UUID(bytes=bytes(identity.device_uuid))
                )
                if identity_available
                else None
            )
            if device_uuid is not None:
                candidate["uuid"] = device_uuid
            observed.append(candidate)
        if deadline.expired():
            raise TimeoutError("Vulkan physical acquisition deadline expired.")
        confirmed = ctypes.c_uint32()
        status = library.vkEnumeratePhysicalDevices(instance, ctypes.byref(confirmed), None)
        if status != 0 or confirmed.value != expected_count:
            raise StateError("Vulkan physical fleet changed during acquisition.")
        confirmed_devices = (ctypes.c_void_p * confirmed.value)()
        status = library.vkEnumeratePhysicalDevices(
            instance, ctypes.byref(confirmed), confirmed_devices
        )
        if (
            status != 0
            or confirmed.value != expected_count
            or tuple(confirmed_devices) != tuple(devices)
        ):
            raise StateError("Vulkan physical fleet handles changed during acquisition.")
        if deadline.expired():
            raise TimeoutError("Vulkan physical acquisition deadline expired.")
        return tuple(observed)
    finally:
        library.vkDestroyInstance(instance, None)


def load_vulkan_library() -> ctypes.CDLL:
    library_name = {
        "Linux": "libvulkan.so.1",
        "Windows": "vulkan-1.dll",
        "Darwin": "libvulkan.1.dylib",
    }.get(platform.system())
    if library_name is None:
        raise OSError("Vulkan has no loader for this host platform.")
    return ctypes.CDLL(library_name)


def _pci_bdf_full(domain: int, address: tuple[int, int, int]) -> str | None:
    bus, device, function = address
    if bus > 0xFF or device > 0x1F or function > 0x7:
        return None
    return f"{domain:08x}:{bus:02x}:{device:02x}.{function}"
