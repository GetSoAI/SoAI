"""SoAI - Intel GPU detection via XPU-SMI [backend/hardware/vendors/intel/gpu_info.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.validation.text_numbers import coerce_float_from_text
from hardware.gpu_inventory.entries import apply_gpu_clock_metrics, build_gpu_entry
from hardware.gpu_inventory.memory_metrics import (
    bytes_to_mebibytes,
    coerce_nonnegative_memory_bytes,
    memory_percent_used,
)
from hardware.operations import create_device_id
from hardware.vendors.intel.commands import execute_intel_dump_json
from hardware.vendors.intel.runtime import is_xpu_smi_available

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("query_intel_gpus",)

LOGGER_NAME = "SoAI.hardware.vendors.intel_gpu_info"
OPERATION = "hardware_intel.query_intel_gpus"


def query_intel_gpus(
    executor: CommandExecutorProtocol,
    detailed: bool,
) -> tuple[list[JSONDict], JSONDict]:
    intel_logger = get_logger(LOGGER_NAME)
    if not is_xpu_smi_available():
        return ([], {})
    gpus: list[JSONDict] = []
    drivers: JSONDict = {}
    try:
        payload = execute_intel_dump_json(executor)
        devices_root = payload.get("devices") if isinstance(payload, dict) else None
        devices = devices_root if isinstance(devices_root, list) else []
        for device_index, device_value in enumerate(devices):
            if not isinstance(device_value, dict):
                continue
            _append_intel_gpu_entry(gpus, device_index, device_value, detailed, intel_logger)
        if isinstance(payload, dict) and "level_zero_version" in payload:
            drivers["Level Zero"] = {
                "version": payload["level_zero_version"],
                "driver_version": payload.get("driver_version"),
            }
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            intel_logger,
            exception,
            message="xpu-smi GPU inventory query failed (non-critical).",
            operation=OPERATION,
            level="warning",
        )
    except ValidationError as exception:
        log_exception(
            intel_logger,
            exception,
            message="Failed to parse xpu-smi output",
            operation=OPERATION,
        )
    return (gpus, drivers)


def _append_intel_gpu_entry(
    gpus: list[JSONDict],
    device_index: int,
    device: JSONDict,
    detailed: bool,
    intel_logger: LoggerProtocol,
) -> None:
    total_mem = coerce_nonnegative_memory_bytes(device.get("memory_physical_size", 0))
    used_mem = coerce_nonnegative_memory_bytes(device.get("memory_used", 0))
    core_clock = coerce_float_from_text(
        device.get("frequency_current")
        or device.get("core_frequency")
        or device.get("compute_frequency"),
    )
    mem_clock = coerce_float_from_text(
        device.get("memory_frequency") or device.get("dram_frequency"),
    )
    device_name = _resolve_intel_device_name(device)
    primary_device_id = _resolve_intel_primary_device_id(device)
    if primary_device_id is None:
        log_exception(
            intel_logger,
            StateError(f"Intel GPU UUID is required for device identity (index {device_index})."),
            message="Skipping Intel GPU entry without a valid UUID.",
            operation=OPERATION,
        )
        return
    pids_value = device.get("pids", [])
    pids = pids_value if isinstance(pids_value, list) else []
    gpu_entry = build_gpu_entry(
        vendor="intel",
        index=device_index,
        vendor_id=device_index,
        device_id=create_device_id("gpu", primary_device_id),
        name=device_name,
        memory_used_mb=bytes_to_mebibytes(used_mem),
        memory_total_mb=bytes_to_mebibytes(total_mem),
        percent_used=memory_percent_used(used_mem, total_mem),
        temperature=coerce_float_from_text(device.get("ras_gpu_temperature")),
        utilization=coerce_float_from_text(device.get("ras_gpu_utilization")),
        power_draw_watts=coerce_float_from_text(device.get("power")),
        power_limit_watts=coerce_float_from_text(device.get("power_limit")),
        processes=(
            [{"pid": pid, "name": "N/A", "used_memory_mb": 0} for pid in pids] if detailed else []
        ),
    )
    gpu_entry["gpu_uuid"] = primary_device_id
    apply_gpu_clock_metrics(gpu_entry, core_clock, mem_clock)
    gpus.append(gpu_entry)


def _resolve_intel_device_name(device: JSONDict) -> str:
    device_name_value = device.get("device_name")
    return (
        device_name_value
        if isinstance(device_name_value, str) and device_name_value
        else "Intel GPU"
    )


def _resolve_intel_primary_device_id(device: JSONDict) -> str | None:
    for candidate_key in ("uuid", "guid", "gpu_uuid", "device_uuid", "global_uuid"):
        candidate_value = device.get(candidate_key)
        if candidate_value is None:
            continue
        candidate_text = str(candidate_value).strip()
        if candidate_text:
            return f"intel-{candidate_text}"
    return None
