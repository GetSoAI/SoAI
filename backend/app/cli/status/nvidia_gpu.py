"""SoAI - CLI status NVIDIA GPU inspection [backend/app/cli/status/nvidia_gpu.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.cli.status.types import NvidiaGpuInfo
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.system.commands import run_argv_capture
from hardware.gpu_inventory.executable_resolution import acquire_gpu_executable
from hardware.vendors.nvidia.smi_values import (
    parse_smi_csv_rows,
    parse_smi_int,
    parse_smi_number,
)

__all__ = ("get_gpu_info_nvidia_quick",)

LOGGER_NAME = "SoAI.app.cli.nvidia_gpu"
OPERATION = "app.cli.status.get_gpu_info_nvidia_quick"
QUERY_FIELDS = (
    "index",
    "name",
    "utilization.gpu",
    "memory.used",
    "memory.total",
    "temperature.gpu",
)


def get_gpu_info_nvidia_quick() -> list[NvidiaGpuInfo] | None:
    resolution = acquire_gpu_executable("nvidia-smi")
    nvidia_smi_path = resolution.path
    if nvidia_smi_path is None:
        return None
    logger = get_logger(LOGGER_NAME)
    try:
        result = run_argv_capture(
            [
                nvidia_smi_path,
                f"--query-gpu={','.join(QUERY_FIELDS)}",
                "--format=csv,noheader,nounits",
            ],
            timeout=5,
        )
        if result.return_code != 0:
            return None
        gpu_list: list[NvidiaGpuInfo] = []
        seen_indexes: set[int] = set()
        for row in parse_smi_csv_rows(result.stdout, field_count=len(QUERY_FIELDS), logger=logger):
            index = parse_smi_int(row[0])
            if index is None or index in seen_indexes or not row[1]:
                logger.trace("Skipping nvidia-smi row without a valid GPU identity: %s", row)
                continue
            seen_indexes.add(index)
            gpu_list.append(
                NvidiaGpuInfo(
                    index=index,
                    name=row[1],
                    utilization_percent=parse_smi_number(row[2]),
                    memory_used_mb=parse_smi_int(row[3]),
                    memory_total_mb=parse_smi_int(row[4]),
                    temperature_c=parse_smi_number(row[5]),
                ),
            )
        return gpu_list or None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to query nvidia-smi (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        return None
