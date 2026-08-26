"""SoAI - NVIDIA GPU discovery and metrics collection via nvidia-smi [backend/hardware/vendors/nvidia/smi_scan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

from core.logging.protocols import TraceLogger
from core.system.commands import run_argv_capture
from core.validation.text_numbers import coerce_float_from_text
from hardware.gpu_inventory.entries import apply_gpu_clock_metrics, build_gpu_entry
from hardware.gpu_inventory.identity import normalize_pci_bdf
from hardware.gpu_inventory.memory_metrics import memory_percent_used
from hardware.operations import create_device_id
from hardware.vendors.nvidia.smi_runtime_info import query_nvidia_smi_runtime_info

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


def _parse_smi_number(raw_value: str) -> float | None:
    normalized = raw_value.strip()
    if (not normalized) or normalized.lower() in {"[not supported]", "n/a", "not supported"}:
        return None
    return coerce_float_from_text(normalized, default=None)


def _parse_smi_int(raw_value: str) -> int:
    numeric_value = _parse_smi_number(raw_value)
    if numeric_value is None:
        return 0
    parsed_value = int(numeric_value)
    if parsed_value < 0:
        return 0
    return parsed_value


def _parse_nvidia_smi_csv(stdout: str, *, logger: TraceLogger) -> list[list[str]]:
    rows: list[list[str]] = []
    csv_reader = csv.reader(io.StringIO(stdout))
    for raw_row in csv_reader:
        normalized_row = [value.strip() for value in raw_row]
        if not normalized_row or all(not value for value in normalized_row):
            continue
        if len(normalized_row) != len(_SMI_QUERY_FIELDS):
            logger.trace(
                "nvidia-smi returned %s fields, expected %s: %s",
                len(normalized_row),
                len(_SMI_QUERY_FIELDS),
                normalized_row,
            )
            continue
        rows.append(normalized_row)
    return rows


def query_nvidia_gpus_via_smi(
    detailed: bool,
    *,
    nvml_gate: NvmlGateProtocol,
    capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
) -> tuple[list[JSONDict], JSONDict]:
    _ = detailed
    logger = nvml_gate.logger
    capabilities_cache_service.clear()
    result = run_argv_capture(
        [
            "nvidia-smi",
            f"--query-gpu={','.join(_SMI_QUERY_FIELDS)}",
            "--format=csv,noheader,nounits",
        ],
        timeout=5,
    )
    if result.return_code != 0:
        logger.trace("nvidia-smi scan unavailable: %s", result.stderr.strip())
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
    for device_index, row in enumerate(_parse_nvidia_smi_csv(result.stdout, logger=logger)):
        uuid_value = row[0]
        if not uuid_value:
            logger.trace("Skipping NVIDIA GPU without UUID in nvidia-smi scan.")
            continue
        pci_bdf = normalize_pci_bdf(row[1])
        gpu_name = row[2] if row[2] else "NVIDIA GPU"
        memory_total_mb = _parse_smi_int(row[3])
        memory_used_mb = _parse_smi_int(row[4])
        percent_used = memory_percent_used(memory_used_mb, memory_total_mb)
        gpu_entry = build_gpu_entry(
            vendor="nvidia",
            index=device_index,
            vendor_id=device_index,
            device_id=create_device_id("gpu", f"nvidia-{uuid_value}"),
            name=gpu_name,
            memory_used_mb=memory_used_mb,
            memory_total_mb=memory_total_mb,
            percent_used=percent_used,
            temperature=_parse_smi_number(row[5]),
            utilization=_parse_smi_number(row[6]),
            power_draw_watts=_parse_smi_number(row[7]),
            power_limit_watts=_parse_smi_number(row[8]),
            processes=[],
        )
        apply_gpu_clock_metrics(
            gpu_entry,
            _parse_smi_number(row[9]),
            _parse_smi_number(row[10]),
        )
        if pci_bdf:
            gpu_entry["pci_bdf"] = pci_bdf
        gpu_entry["gpu_uuid"] = uuid_value
        driver_version = row[11]
        if driver_version and "NVIDIA_Driver" not in drivers:
            drivers["NVIDIA_Driver"] = {
                "version": driver_version,
                "driver_version": driver_version,
            }
        gpus.append(gpu_entry)
    return (gpus, drivers)
