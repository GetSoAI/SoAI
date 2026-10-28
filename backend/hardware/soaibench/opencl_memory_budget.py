"""SoAI - OpenCL allocation and retained-buffer budget [backend/hardware/soaibench/opencl_memory_budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("opencl_buffer_capacity_bytes",)

MAX_DEVICE_MEMORY_PERCENT = 72


def opencl_buffer_capacity_bytes(
    global_mem_bytes: int, max_alloc_bytes: int, *, retained_bytes: int = 0
) -> int:
    return max(
        0,
        min(
            global_mem_bytes * MAX_DEVICE_MEMORY_PERCENT // 100 - retained_bytes,
            max_alloc_bytes,
        ),
    )
