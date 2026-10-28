"""SoAI - Vulkan GPU capability observation through physical binding [backend/hardware/gpu_inventory/vulkan_physical_acquisition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.hardware.gpu_physical_observations import read_gpu_physical_identity
from core.hardware.vulkan_physical_acquisition import (
    acquire_vulkan_physical_devices,
    load_vulkan_library,
)
from core.hardware.windows_adapter_address import load_windows_adapter_library
from core.logging.trace import get_logger
from core.types.json import JSONDict
from hardware.gpu_inventory.physical_binding import resolve_gpu_physical_binding

__all__ = ("observe_vulkan_gpu_capabilities",)

LOGGER_NAME = "SoAI.hardware.gpu_inventory.vulkan_physical_acquisition"
OPERATION = "hardware.vulkan.physical_acquisition"
VULKAN_GPU_DEVICE_TYPES = (1, 2)


def observe_vulkan_gpu_capabilities(
    gpus: list[JSONDict], library: ctypes.CDLL | None = None
) -> None:
    if not gpus:
        return
    try:
        devices = tuple(
            device
            for device in acquire_vulkan_physical_devices(
                library if library is not None else load_vulkan_library(),
                load_windows_adapter_library(),
            )
            if device.get("vulkan_device_type") in VULKAN_GPU_DEVICE_TYPES
        )
    except (OSError, TypeError, AttributeError, StateError, ValidationError) as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Vulkan physical GPU capability observation is unavailable.",
            operation=OPERATION,
            level="trace",
        )
        for gpu in gpus:
            gpu["vulkan_supported"] = None
            gpu["vulkan_enumeration_state"] = "degraded"
        return
    for gpu in gpus:
        binding = resolve_gpu_physical_binding(gpu, list(devices))
        unbound_vendor_devices = any(
            device.get("type") == gpu.get("type") and read_gpu_physical_identity(device) is None
            for device in devices
        )
        contradictory_ids = any(
            any(
                isinstance(device.get(field), str)
                and isinstance(gpu.get(field), str)
                and str(device[field]).casefold() != str(gpu[field]).casefold()
                for field in ("pci_vendor_id", "pci_device_id")
            )
            and resolve_gpu_physical_binding(gpu, [device]).state == GPUPhysicalBindingState.BOUND
            for device in devices
        )
        if binding.state == GPUPhysicalBindingState.BOUND and not contradictory_ids:
            gpu["vulkan_supported"] = True
        elif (
            unbound_vendor_devices
            or contradictory_ids
            or binding.state
            in (
                GPUPhysicalBindingState.IDENTITY_CONFLICT,
                GPUPhysicalBindingState.INVALID_RESPONSE,
                GPUPhysicalBindingState.IDENTITY_UNAVAILABLE,
            )
        ):
            gpu["vulkan_supported"] = None
        else:
            gpu["vulkan_supported"] = False
        gpu["vulkan_enumeration_state"] = "observed"
