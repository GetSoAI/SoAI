"""SoAI - NVIDIA GPU discovery and metrics collection [backend/hardware/vendors/nvidia/scan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import pynvml

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.logging.rate_limited_logger import RateLimitedLogger
from hardware.gpu_inventory.entries import build_gpu_entry
from hardware.gpu_inventory.identity import uuid_from_device_id
from hardware.vendors.nvidia.internal_protocols import (
    NvmlDeviceGetHandleByIndexProtocol,
    NvmlSystemGetCudaDriverVersionProtocol,
)
from hardware.vendors.nvidia.scan_device_identity import (
    read_gpu_name,
    read_pci_bdf,
    read_primary_device_id,
)
from hardware.vendors.nvidia.scan_errors import (
    is_expected_nvml_device_scan_error,
    is_expected_nvml_unavailable_error,
)
from hardware.vendors.nvidia.scan_metrics.memory import read_memory_metrics
from hardware.vendors.nvidia.scan_metrics.processes import read_processes
from hardware.vendors.nvidia.scan_metrics.sensors import (
    read_core_clock_mhz,
    read_mem_clock_mhz,
    read_power_draw_watts,
    read_power_limit_watts,
    read_temperature,
    read_utilization,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("query_nvidia_gpus",)

OPERATION_HARDWARE_NVIDIA_SYNC_GET_NVIDIA_GPUS = "hardware_nvidia.sync_get_nvidia_gpus"


def query_nvidia_gpus(
    detailed: bool,
    *,
    nvml_gate: NvmlGateProtocol,
    capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
) -> tuple[list[JSONDict], JSONDict]:
    logger = nvml_gate.logger
    expected_unavailable_logger = RateLimitedLogger(interval_seconds=300.0)
    gpus: list[JSONDict] = []
    drivers: JSONDict = {}
    sequence = capabilities_cache_service.expire_inventory_snapshot()
    complete = False
    driver_version = ""
    try:
        with nvml_gate.session():
            try:
                driver_version = str(pynvml.nvmlSystemGetDriverVersion())
                try:
                    cuda_version_function = pynvml.nvmlSystemGetCudaDriverVersion
                except AttributeError:
                    cuda_version_function = None
                if isinstance(cuda_version_function, NvmlSystemGetCudaDriverVersionProtocol):
                    cuda_version_val = cuda_version_function()
                    drivers["CUDA"] = {
                        "version": f"{cuda_version_val // 1000}.{cuda_version_val % 1000 // 10}",
                        "driver_version": driver_version,
                    }
            except pynvml.NVMLError as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Could not get NVIDIA driver/CUDA version.",
                    operation=OPERATION_HARDWARE_NVIDIA_SYNC_GET_NVIDIA_GPUS,
                    level="trace",
                )
            count = 0
            try:
                count = int(pynvml.nvmlDeviceGetCount())
            except (TypeError, ValueError) as exception:
                raise StateError("NVIDIA inventory count unavailable.") from exception
            try:
                device_get_handle_by_index = pynvml.nvmlDeviceGetHandleByIndex
            except AttributeError:
                device_get_handle_by_index = None
            for device_index in range(count):
                if not isinstance(device_get_handle_by_index, NvmlDeviceGetHandleByIndexProtocol):
                    raise StateError(
                        "NVML handle lookup unavailable.",
                        operation="hardware.nvidia.scan.get_handle",
                    )
                try:
                    handle = device_get_handle_by_index(device_index)
                except pynvml.NVMLError as exception:
                    if not is_expected_nvml_device_scan_error(exception):
                        raise
                    log_handled_exception(
                        logger,
                        exception,
                        message="Skipping NVIDIA GPU with unavailable NVML handle (non-critical).",
                        operation=OPERATION_HARDWARE_NVIDIA_SYNC_GET_NVIDIA_GPUS,
                        details={"device_index": device_index},
                        level="warning",
                    )
                    continue
                memory_total_mb, memory_used_mb, percent_used = read_memory_metrics(handle)
                temperature = read_temperature(device_index, handle, logger=logger)
                utilization = read_utilization(device_index, handle, logger=logger)
                power_draw_watts = read_power_draw_watts(device_index, handle, logger=logger)
                power_limit_watts = read_power_limit_watts(device_index, handle, logger=logger)
                processes = read_processes(
                    handle,
                    logger=logger,
                    device_index=device_index,
                    detailed=detailed,
                )
                core_clock = read_core_clock_mhz(device_index, handle, logger=logger)
                mem_clock = read_mem_clock_mhz(device_index, handle, logger=logger)
                gpu_name = read_gpu_name(handle)
                device_id = read_primary_device_id(handle, logger=logger, device_index=device_index)
                pci_bdf = read_pci_bdf(handle, logger=logger, device_index=device_index)
                gpu_data = build_gpu_entry(
                    vendor="nvidia",
                    index=device_index,
                    vendor_id=device_index,
                    device_id=device_id,
                    name=gpu_name,
                    memory_used_mb=memory_used_mb,
                    memory_total_mb=memory_total_mb,
                    percent_used=percent_used,
                    temperature=temperature,
                    utilization=utilization,
                    power_draw_watts=power_draw_watts,
                    power_limit_watts=power_limit_watts,
                    processes=processes,
                )
                if core_clock is not None:
                    gpu_data["core_clock_mhz"] = float(core_clock)
                if mem_clock is not None:
                    gpu_data["mem_clock_mhz"] = float(mem_clock)
                if pci_bdf is not None:
                    gpu_data["pci_bdf"] = pci_bdf
                gpu_uuid = uuid_from_device_id(device_id)
                if gpu_uuid is not None:
                    gpu_data["gpu_uuid"] = gpu_uuid
                gpus.append(gpu_data)
            complete = len(gpus) == count
    except pynvml.NVMLError as exception:
        expected_unavailable = is_expected_nvml_unavailable_error(exception)
        if expected_unavailable:
            should_emit, suppressed = expected_unavailable_logger.should_emit()
            if not should_emit:
                return (gpus, drivers)
            log_handled_exception(
                logger,
                exception,
                message="pynvml unavailable during NVIDIA GPU scan (expected) (non-critical).",
                operation=OPERATION_HARDWARE_NVIDIA_SYNC_GET_NVIDIA_GPUS,
                details={"suppressed_repeats": suppressed} if suppressed else None,
                level="trace",
            )
            return (gpus, drivers)
        log_exception(
            logger,
            exception,
            message="pynvml failed during NVIDIA GPU scan",
            operation=OPERATION_HARDWARE_NVIDIA_SYNC_GET_NVIDIA_GPUS,
            level="error",
        )
    finally:
        capabilities_cache_service.observe_inventory(
            sequence,
            "complete" if complete else "failed",
            gpus,
            driver_version,
        )
    return (gpus, drivers)
