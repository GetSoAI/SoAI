"""SoAI - Primary GPU selection for system capabilities [backend/hardware/manager/gpu_primary_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.validation.text_numbers import coerce_float_from_text
from hardware.vendors.vendor_metadata import (
    normalize_vendor_value,
    ready_vendors_from_compute_drivers,
    vendor_priority,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "PrimaryGpuSelection",
    "VendorGpuSummary",
    "select_primary_gpu",
)


@dataclass(slots=True)
class VendorGpuSummary:
    vendor: str
    total_memory_mb: float
    best_gpu_name: str
    best_gpu_memory_mb: float


@dataclass(frozen=True, slots=True)
class PrimaryGpuSelection:
    vendor: str
    name: str
    vram_gb: float


def _coerce_memory_total_mb(value: JSONValue) -> float:
    if isinstance(value, bool):
        return 0.0
    parsed = coerce_float_from_text(value)
    if parsed is None or parsed < 0:
        return 0.0
    return float(parsed)


def _collect_vendor_summaries(gpu_info: JSONDict) -> dict[str, VendorGpuSummary]:
    summaries: dict[str, VendorGpuSummary] = {}
    gpus_value = gpu_info.get("gpus")
    gpus = gpus_value if isinstance(gpus_value, list) else []
    for gpu in gpus:
        if not isinstance(gpu, dict):
            continue
        vendor = normalize_vendor_value(gpu.get("type"))
        if not vendor:
            continue
        memory_total_mb = _coerce_memory_total_mb(gpu.get("memory_total_mb"))
        gpu_name_value = gpu.get("name")
        gpu_name = gpu_name_value if isinstance(gpu_name_value, str) and gpu_name_value else "N/A"
        if vendor not in summaries:
            summaries[vendor] = VendorGpuSummary(
                vendor=vendor,
                total_memory_mb=0.0,
                best_gpu_name=gpu_name,
                best_gpu_memory_mb=memory_total_mb,
            )
        summary = summaries[vendor]
        summary.total_memory_mb += memory_total_mb
        if memory_total_mb > summary.best_gpu_memory_mb:
            summary.best_gpu_memory_mb = memory_total_mb
            summary.best_gpu_name = gpu_name
    return summaries


def select_primary_gpu(gpu_info: JSONDict, compute_drivers: JSONDict) -> PrimaryGpuSelection:
    summaries = _collect_vendor_summaries(gpu_info)
    if not summaries:
        return PrimaryGpuSelection(vendor="none", name="N/A", vram_gb=0.0)
    ready_vendors = ready_vendors_from_compute_drivers(compute_drivers)
    selected_summary = max(
        summaries.values(),
        key=lambda summary: (
            1 if summary.vendor in ready_vendors else 0,
            summary.total_memory_mb,
            vendor_priority(summary.vendor),
        ),
    )
    return PrimaryGpuSelection(
        vendor=selected_summary.vendor,
        name=selected_summary.best_gpu_name,
        vram_gb=round(selected_summary.total_memory_mb / 1024.0, 2),
    )
