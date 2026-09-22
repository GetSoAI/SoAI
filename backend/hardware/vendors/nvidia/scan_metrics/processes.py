"""SoAI - NVIDIA scan process metrics [backend/hardware/vendors/nvidia/scan_metrics/processes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes

import psutil
import pynvml
from pynvml import NVMLLibraryMismatchError

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import TraceLogger
from core.types.json import JSONDict
from hardware.vendors.nvidia.internal_protocols import NvmlProcessInfoProtocol

__all__ = ("read_processes",)

OPERATION = "hardware.nvidia.scan.read_processes"


def _coerce_proc_pid(proc_entry: NvmlProcessInfoProtocol) -> int:
    try:
        pid_value = proc_entry.pid
    except AttributeError:
        return 0
    if not isinstance(pid_value, int):
        return 0
    return pid_value


def _proc_used_gpu_memory_available(proc_entry: NvmlProcessInfoProtocol) -> bool:
    try:
        value = proc_entry.usedGpuMemory
    except AttributeError:
        return False
    return value is not None


def _coerce_proc_used_gpu_memory_mb(proc_entry: NvmlProcessInfoProtocol) -> int:
    try:
        used_value = proc_entry.usedGpuMemory
    except AttributeError:
        return 0
    if used_value is None:
        return 0
    try:
        used_bytes = int(used_value)
    except (TypeError, ValueError):
        return 0
    return used_bytes // 1024**2


def _build_process_entry(proc_entry: NvmlProcessInfoProtocol) -> JSONDict:
    pid = _coerce_proc_pid(proc_entry)
    return {
        "pid": pid,
        "used_memory_mb": (
            _coerce_proc_used_gpu_memory_mb(proc_entry)
            if _proc_used_gpu_memory_available(proc_entry)
            else 0
        ),
        "name": psutil.Process(pid).name() if psutil.pid_exists(pid) else "N/A",
    }


def _read_compute_process_entries(handle: ctypes.c_void_p) -> list[NvmlProcessInfoProtocol]:
    try:
        device_get_compute_running_processes = pynvml.nvmlDeviceGetComputeRunningProcesses
    except AttributeError:
        device_get_compute_running_processes = None
    if not callable(device_get_compute_running_processes):
        return []
    try:
        proc_entries_raw = device_get_compute_running_processes(handle)
    except NVMLLibraryMismatchError:
        try:
            versioned_device_get_compute_running_processes = (
                pynvml.nvmlDeviceGetComputeRunningProcesses_v2
            )
        except AttributeError as exception:
            raise NVMLLibraryMismatchError(
                "The versioned NVIDIA compute process reader is unavailable."
            ) from exception
        if not callable(versioned_device_get_compute_running_processes):
            return []
        proc_entries_raw = versioned_device_get_compute_running_processes(handle)
    if isinstance(proc_entries_raw, list | tuple):
        return [*proc_entries_raw]
    return []


def read_processes(
    handle: ctypes.c_void_p,
    *,
    logger: TraceLogger,
    device_index: int,
    detailed: bool,
) -> list[JSONDict]:
    if not detailed:
        return []
    try:
        proc_entries = _read_compute_process_entries(handle)
        return [_build_process_entry(proc_entry) for proc_entry in proc_entries]
    except NVMLLibraryMismatchError as exception:
        log_handled_exception(
            logger,
            exception,
            message="NVIDIA process metrics are unavailable with this driver/NVML library (non-critical).",
            operation=OPERATION,
            details={"device_index": device_index},
            level="trace",
        )
        return []
    except (pynvml.NVMLError, psutil.Error) as exception:
        try:
            nvml_error_not_supported = pynvml.NVML_ERROR_NOT_SUPPORTED
        except AttributeError:
            nvml_error_not_supported = None
        exception_value = exception.value if isinstance(exception, pynvml.NVMLError) else None
        if not (
            isinstance(exception, pynvml.NVMLError) and exception_value == nvml_error_not_supported
        ):
            log_handled_exception(
                logger,
                exception,
                message="Could not get processes for GPU.",
                operation=OPERATION,
                details={"device_index": device_index},
                level="trace",
            )
        return []
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read NVIDIA processes (non-critical).",
            operation=OPERATION,
            details={"device_index": device_index},
            level="trace",
        )
        return []
