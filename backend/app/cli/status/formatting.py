"""SoAI - CLI status formatting utilities [backend/app/cli/status/formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from app.cli.status.types import NvidiaGpuInfo

__all__ = (
    "format_load_average",
    "format_nvidia_gpu_readings",
    "format_uptime",
)

LOGGER_NAME = "SoAI.app.cli.formatting"
OPERATION = "app.cli.status.format_load_average"
UNAVAILABLE = "unavailable"


def format_uptime(uptime_ms: float) -> str:
    uptime_seconds = float(uptime_ms) / 1000.0
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    parts: list[str] = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def format_load_average() -> str:
    if sys.platform == "win32":
        return ""
    try:
        load1, load5, load15 = os.getloadavg()
        return f", load {load1:.2f} {load5:.2f} {load15:.2f}"
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to get load average (non-critical).",
            operation=OPERATION,
            level="trace",
        )
        return ""


def format_nvidia_gpu_readings(gpu: NvidiaGpuInfo) -> str:
    utilization = (
        f"{int(gpu.utilization_percent)}% util"
        if gpu.utilization_percent is not None
        else f"util {UNAVAILABLE}"
    )
    temperature = (
        f"{int(gpu.temperature_c)}°C"
        if gpu.temperature_c is not None
        else f"temperature {UNAVAILABLE}"
    )
    memory_used = UNAVAILABLE if gpu.memory_used_mb is None else str(gpu.memory_used_mb)
    memory_total = UNAVAILABLE if gpu.memory_total_mb is None else str(gpu.memory_total_mb)
    return f"{utilization}, {memory_used} / {memory_total} MB VRAM, {temperature}"
