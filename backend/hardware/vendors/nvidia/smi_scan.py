"""SoAI - NVIDIA GPU discovery and metrics collection via nvidia-smi [backend/hardware/vendors/nvidia/smi_scan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.system.commands import run_argv_capture
from hardware.gpu_inventory.entries import apply_gpu_clock_metrics, build_gpu_entry
from hardware.gpu_inventory.executable_resolution import acquire_gpu_executable
from hardware.gpu_inventory.identity import normalize_pci_bdf
from hardware.gpu_inventory.memory_metrics import memory_percent_used
from hardware.operations import create_device_id
from hardware.vendors.nvidia.smi_runtime_info import query_nvidia_smi_runtime_info
from hardware.vendors.nvidia.smi_values import (
    parse_smi_csv_rows,
    parse_smi_int,
    parse_smi_number,
)

if TYPE_CHECKING:
    from core.hardware.protocols import (
        NvidiaCapabilitiesCacheServiceProtocol,
        NvmlGateProtocol,
    )
    from core.types.json import JSONDict

__all__ = ()

_SMI_QUERY_FIELDS: tuple[str, ...] = (
    "uuid",
    "pci.bus_id",
    "name",
    "memory.total",
    "memory.used",
    "temperature.gpu",
    "utilization.gpu",
    "power.draw",
    "power.limit",
    "clocks.gr",
    "clocks.mem",
    "driver_version",
)


def query_nvidia_gpus_via_smi(
    detailed: bool,
    *,
    nvml_gate: NvmlGateProtocol,
    capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    on_inventory_observed: Callable[[Literal["complete", "partial", "failed"]], None] | None = None,
) -> tuple[list[JSONDict], JSONDict]:
    _ = detailed
    logger = nvml_gate.logger
    sequence = capabilities_cache_service.expire_inventory_snapshot()
    resolution = acquire_gpu_executable("nvidia-smi")
    if resolution.path is None:
        logger.trace("nvidia-smi executable unavailable: %s", resolution.state.value)
        capabilities_cache_service.observe_inventory(sequence, "failed", [], "")
        if on_inventory_observed is not None:
            on_inventory_observed("failed")
        return ([], {})
    result = run_argv_capture(
        [
            resolution.path,
            f"--query-gpu={','.join(_SMI_QUERY_FIELDS)}",
            "--format=csv,noheader,nounits",
        ],
        timeout=5,
    )
    if result.return_code != 0:
        logger.trace("nvidia-smi scan unavailable: %s", result.stderr.strip())
        capabilities_cache_service.observe_inventory(sequence, "failed", [], "")
        if on_inventory_observed is not None:
            on_inventory_observed("failed")
        return ([], {})
    drivers: JSONDict = {}
    gpus: list[JSONDict] = []
    runtime_info = query_nvidia_smi_runtime_info()
    if runtime_info is not None:
        if runtime_info.driver_version:
            drivers["NVIDIA_Driver"] = {
                "version": runtime_info.driver_version,
                "driver_version": runtime_info.driver_version,
            }
        if runtime_info.cuda_version:
            drivers["CUDA"] = {
                "version": runtime_info.cuda_version,
                "driver_version": runtime_info.driver_version or runtime_info.cuda_version,
            }
    rows = parse_smi_csv_rows(result.stdout, field_count=len(_SMI_QUERY_FIELDS), logger=logger)
    complete = len(rows) == len([line for line in result.stdout.splitlines() if line.strip()])
    driver_version = ""
    for device_index, row in enumerate(rows):
        uuid_value = row[0]
        if not uuid_value:
            complete = False
            logger.trace("Skipping NVIDIA GPU without UUID in nvidia-smi scan.")
            continue
        pci_bdf = normalize_pci_bdf(row[1])
        gpu_name = row[2] if row[2] else "NVIDIA GPU"
        memory_total_mb = parse_smi_int(row[3])
        memory_used_mb = parse_smi_int(row[4])
        percent_used = (
            memory_percent_used(memory_used_mb, memory_total_mb)
            if memory_used_mb is not None and memory_total_mb is not None and memory_total_mb > 0
            else None
        )
        gpu_entry = build_gpu_entry(
            vendor="nvidia",
            index=device_index,
            vendor_id=device_index,
            device_id=create_device_id("gpu", f"nvidia-{uuid_value}"),
            name=gpu_name,
            memory_used_mb=memory_used_mb if memory_used_mb is not None else 0,
            memory_total_mb=memory_total_mb if memory_total_mb is not None else 0,
            percent_used=percent_used if percent_used is not None else 0.0,
            temperature=parse_smi_number(row[5]),
            utilization=parse_smi_number(row[6]),
            power_draw_watts=parse_smi_number(row[7]),
            power_limit_watts=parse_smi_number(row[8]),
            processes=[],
        )
        gpu_entry.update(
            {
                "memory_used_mb": memory_used_mb,
                "memory_total_mb": memory_total_mb,
                "percent_used": percent_used,
                "memory_total_source": "nvidia-smi.memory.total",
                "memory_total_unit": "MiB",
                "memory_total_reported_value": memory_total_mb,
            }
        )
        apply_gpu_clock_metrics(
            gpu_entry,
            parse_smi_number(row[9]),
            parse_smi_number(row[10]),
        )
        if pci_bdf:
            gpu_entry["pci_bdf"] = pci_bdf
        gpu_entry["pci_bdf_observations"] = [row[1]] if row[1] else []
        if normalize_observed_full_pci_bdf(row[1]):
            gpu_entry["pci_bdf_full"] = row[1]
        gpu_entry["gpu_uuid"] = uuid_value
        driver_version = row[11]
        if driver_version and "NVIDIA_Driver" not in drivers:
            drivers["NVIDIA_Driver"] = {
                "version": driver_version,
                "driver_version": driver_version,
            }
        gpus.append(gpu_entry)
    capabilities_cache_service.observe_inventory(
        sequence,
        "complete" if complete else "partial",
        gpus,
        driver_version,
    )
    if on_inventory_observed is not None:
        on_inventory_observed("complete" if complete else "partial")
    return (gpus, drivers)
