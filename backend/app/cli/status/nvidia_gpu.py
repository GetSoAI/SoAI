"""SoAI - CLI status NVIDIA GPU inspection [backend/app/cli/status/nvidia_gpu.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import shutil

from app.cli.status.types import NvidiaGpuInfo
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.system.commands import run_argv_capture

__all__ = ("get_gpu_info_nvidia_quick",)

LOGGER_NAME = "SoAI.app.cli.nvidia_gpu"
OPERATION = "app.cli.status.get_gpu_info_nvidia_quick"


def get_gpu_info_nvidia_quick() -> list[NvidiaGpuInfo] | None:
    nvidia_smi_path = shutil.which("nvidia-smi")
    if not nvidia_smi_path:
        return None
    try:
        result = run_argv_capture(
            [
                nvidia_smi_path,
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            timeout=5,
        )
        if result.return_code != 0:
            return None
        gpu_list: list[NvidiaGpuInfo] = []
        for line in result.stdout.strip().split("\n"):
            stripped_line = line.strip()
            if not stripped_line:
                continue
            parts = [part.strip() for part in stripped_line.split(",")]
            if len(parts) < 6:
                continue
            gpu_list.append(
                NvidiaGpuInfo(
                    index=int(parts[0]),
                    name=parts[1],
                    utilization_percent=float(parts[2]) if parts[2] else 0.0,
                    memory_used_mb=float(parts[3]) if parts[3] else 0.0,
                    memory_total_mb=float(parts[4]) if parts[4] else 0.0,
                    temperature_c=float(parts[5]) if parts[5] else 0.0,
                ),
            )
        return gpu_list or None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to query nvidia-smi (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        return None
