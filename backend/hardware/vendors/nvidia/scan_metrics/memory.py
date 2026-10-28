"""SoAI - NVIDIA scan memory metrics [backend/hardware/vendors/nvidia/scan_metrics/memory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from dataclasses import dataclass

import pynvml

from core.errors.exception_logging import log_handled_exception
from core.logging.trace import get_logger
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from hardware.gpu_inventory.memory_metrics import (
    bytes_to_mebibytes,
    memory_percent_used,
)

LOGGER_NAME = "SoAI.hardware.vendors.memory"
OPERATION_HARDWARE_NVIDIA_SCAN_MEMORY = "hardware.nvidia.scan.memory"


__all__ = ("read_memory_metrics",)


@dataclass(frozen=True, slots=True)
class NvidiaMemoryMetrics:
    total_bytes: int | None
    used_bytes: int | None
    total_mb: int | None
    used_mb: int | None
    percent_used: float | None


def read_memory_metrics(handle: ctypes.c_void_p) -> NvidiaMemoryMetrics:
    try:
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    except pynvml.NVMLError as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Optional NVIDIA memory observation unavailable.",
            operation=OPERATION_HARDWARE_NVIDIA_SCAN_MEMORY,
            level="trace",
        )
        return NvidiaMemoryMetrics(None, None, None, None, None)
    try:
        memory_total = coerce_optional_non_negative_int_strict(mem_info.total)
    except AttributeError:
        memory_total = None
    try:
        memory_used = coerce_optional_non_negative_int_strict(mem_info.used)
    except AttributeError:
        memory_used = None
    return NvidiaMemoryMetrics(
        memory_total,
        memory_used,
        bytes_to_mebibytes(memory_total) if memory_total is not None else None,
        bytes_to_mebibytes(memory_used) if memory_used is not None else None,
        (
            memory_percent_used(memory_used, memory_total)
            if memory_used is not None and memory_total is not None and memory_total > 0
            else None
        ),
    )
