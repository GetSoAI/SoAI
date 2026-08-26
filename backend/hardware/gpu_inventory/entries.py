"""SoAI - GPU inventory entry construction [backend/hardware/gpu_inventory/entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "apply_gpu_clock_metrics",
    "build_gpu_entry",
)


def apply_gpu_clock_metrics(
    gpu_entry: JSONDict,
    core_clock: float | None,
    mem_clock: float | None,
) -> None:
    if core_clock is not None:
        gpu_entry["core_clock_mhz"] = core_clock
    if mem_clock is not None:
        gpu_entry["mem_clock_mhz"] = mem_clock


def build_gpu_entry(
    *,
    vendor: str,
    index: int,
    vendor_id: JSONValue,
    device_id: str | None = None,
    name: str,
    memory_used_mb: int,
    memory_total_mb: int,
    percent_used: float,
    temperature: float | None = None,
    utilization: float | None = None,
    power_draw_watts: float | None = None,
    power_limit_watts: float | None = None,
    processes: list[JSONDict] | None = None,
) -> JSONDict:
    return {
        "type": vendor,
        "index": index,
        "vendor_id": vendor_id,
        "device_id": device_id,
        "name": name,
        "memory_used_mb": memory_used_mb,
        "memory_total_mb": memory_total_mb,
        "percent_used": percent_used,
        "temperature": temperature,
        "utilization": utilization,
        "power_draw_watts": power_draw_watts,
        "power_limit_watts": power_limit_watts,
        "processes": list(processes) if processes is not None else [],
    }
