"""SoAI - Physically matched Windows NVIDIA utilization [backend/hardware/vendors/nvidia/nvapi_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_physical_observations import (
    read_gpu_pci_observations,
    read_gpu_physical_identity,
)
from core.types.json import JSONDict
from hardware.vendors.nvidia.nvapi_function_acquisition import resolve_nvapi_function
from hardware.vendors.nvidia.nvapi_physical_binding import bind_nvapi_physical_devices
from hardware.vendors.nvidia.nvapi_sensor_types import NvApiDynamicPstates

if TYPE_CHECKING:
    from core.hardware.protocols import NvmlGateProtocol

__all__ = ("enrich_nvapi_utilization",)

OPERATION_HARDWARE_NVIDIA_NVAPI_TELEMETRY_UTILIZATION = (
    "hardware.nvidia.nvapi_telemetry.utilization"
)


def enrich_nvapi_utilization(gpus: list[JSONDict], gate: NvmlGateProtocol) -> None:
    if not gpus or not gate.runtime_platform.is_windows:
        return
    if all(gpu.get("utilization") is not None for gpu in gpus):
        return
    failures: tuple[type[Exception], ...] = (
        StateError,
        ValidationError,
        ctypes.ArgumentError,
        *RECOVERABLE_EXCEPTIONS,
    )
    try:
        query = gate.nvapi_support.native_query_interface
        if query is None:
            return
        enumerate_gpus = resolve_nvapi_function("NvAPI_EnumPhysicalGPUs", query_interface=query)
        read_bus = resolve_nvapi_function("NvAPI_GPU_GetBusId", query_interface=query)
        read_utilization = resolve_nvapi_function(
            "NvAPI_GPU_GetDynamicPstatesInfoEx", query_interface=query
        )
        if enumerate_gpus is None or read_bus is None or read_utilization is None:
            return
        devices: list[GPUPhysicalDevice] = []
        for gpu in gpus:
            identity = read_gpu_physical_identity(gpu)
            device_id = gpu.get("device_id")
            if identity is None or not isinstance(device_id, str):
                raise StateError("NvAPI sensor inventory requires observed physical identities.")
            devices.append(
                GPUPhysicalDevice(
                    device_id, "nvidia", identity, None, None, tuple(read_gpu_pci_observations(gpu))
                )
            )
        bound = bind_nvapi_physical_devices(
            tuple(devices), enumerate_gpus=enumerate_gpus, read_bus=read_bus
        )
        samples: dict[str, int] = {}
        for device, gpu in zip(bound, gpus, strict=True):
            if gpu.get("utilization") is not None:
                continue
            output = NvApiDynamicPstates()
            version = ctypes.sizeof(NvApiDynamicPstates) | (1 << 16)
            output.version = version
            status = read_utilization(device.handle, ctypes.pointer(output))
            if status != 0:
                gate.logger.trace(
                    "NvAPI GPU utilization unavailable for %s: native_status=%s",
                    device.device.device_id,
                    status,
                )
                continue
            domain = output.utilization[0]
            if output.version != version or domain.present not in (0, 1) or domain.percentage > 100:
                gate.logger.warning(
                    "NvAPI GPU utilization response is invalid for %s", device.device.device_id
                )
                continue
            if domain.present == 1:
                samples[device.device.device_id] = domain.percentage
        current = bind_nvapi_physical_devices(
            tuple(devices), enumerate_gpus=enumerate_gpus, read_bus=read_bus
        )
        if tuple((row.device, row.handle.value) for row in current) != tuple(
            (row.device, row.handle.value) for row in bound
        ):
            raise StateError("NvAPI physical handles changed during sensor acquisition.")
        for gpu in gpus:
            device_id = gpu.get("device_id")
            if isinstance(device_id, str) and device_id in samples:
                gpu["utilization"] = samples[device_id]
    except failures as exception:
        log_handled_exception(
            gate.logger,
            exception,
            message="Optional NvAPI GPU utilization acquisition unavailable.",
            operation=OPERATION_HARDWARE_NVIDIA_NVAPI_TELEMETRY_UTILIZATION,
            level="trace",
        )
