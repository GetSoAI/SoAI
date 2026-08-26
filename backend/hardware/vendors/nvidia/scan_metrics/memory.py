"""SoAI - NVIDIA scan memory metrics [backend/hardware/vendors/nvidia/scan_metrics/memory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes

import pynvml

from hardware.gpu_inventory.memory_metrics import (
    bytes_to_mebibytes,
    coerce_nonnegative_memory_bytes,
    memory_percent_used,
)

__all__ = ("read_memory_metrics",)


def read_memory_metrics(handle: ctypes.c_void_p) -> tuple[int, int, float]:
    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    try:
        memory_total = coerce_nonnegative_memory_bytes(mem_info.total)
    except AttributeError:
        memory_total = 0
    try:
        memory_used = coerce_nonnegative_memory_bytes(mem_info.used)
    except AttributeError:
        memory_used = 0
    return (
        bytes_to_mebibytes(memory_total),
        bytes_to_mebibytes(memory_used),
        memory_percent_used(memory_used, memory_total),
    )
