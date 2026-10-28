"""SoAI - NVIDIA runtime driver and CUDA info via nvidia-smi [backend/hardware/vendors/nvidia/smi_runtime_info.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass

from core.system.commands import run_argv_capture
from hardware.gpu_inventory.executable_resolution import acquire_gpu_executable

__all__ = (
    "NvidiaSmiRuntimeInfo",
    "query_nvidia_smi_runtime_info",
)


def _cuda_version_pattern() -> re.Pattern[str]:
    return re.compile("CUDA Version:\\s*([0-9]+(?:\\.[0-9]+)?)")


@dataclass(frozen=True, slots=True)
class NvidiaSmiRuntimeInfo:
    driver_version: str | None
    cuda_version: str | None


def _query_driver_version(executable_path: str) -> str | None:
    result = run_argv_capture(
        [executable_path, "--query-gpu=driver_version", "--format=csv,noheader,nounits"],
        timeout=5,
    )
    if result.return_code != 0:
        return None
    for line in result.stdout.splitlines():
        driver_version = line.strip()
        if driver_version:
            return driver_version
    return None


def _query_cuda_version(executable_path: str) -> str | None:
    result = run_argv_capture([executable_path], timeout=5)
    if result.return_code != 0:
        return None
    match = _cuda_version_pattern().search(result.stdout)
    if match is None:
        return None
    return match.group(1)


def query_nvidia_smi_runtime_info() -> NvidiaSmiRuntimeInfo | None:
    resolution = acquire_gpu_executable("nvidia-smi")
    if resolution.path is None:
        return None
    driver_version = _query_driver_version(resolution.path)
    cuda_version = _query_cuda_version(resolution.path)
    if driver_version is None and cuda_version is None:
        return None
    return NvidiaSmiRuntimeInfo(
        driver_version=driver_version,
        cuda_version=cuda_version,
    )
