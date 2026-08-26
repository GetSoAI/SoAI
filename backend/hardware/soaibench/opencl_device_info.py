"""SoAI - SoAIBench OpenCL device metadata [backend/hardware/soaibench/opencl_device_info.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("OpenCLDeviceInfo",)


@dataclass(frozen=True, slots=True)
class OpenCLDeviceInfo:
    platform_name: str
    platform_vendor: str
    device_name: str
    device_vendor: str
    driver_version: str
    global_mem_bytes: int
    max_alloc_bytes: int
