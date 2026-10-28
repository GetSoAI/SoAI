"""SoAI - Intel GPU detection via XPU-SMI [backend/hardware/vendors/intel/gpu_info.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.logging.trace import get_logger
from core.validation.integers import coerce_non_negative_exact_int_or_none
from core.validation.text_numbers import coerce_float_from_text
from hardware.gpu_inventory.entries import apply_gpu_clock_metrics, build_gpu_entry
from hardware.gpu_inventory.memory_metrics import (
    bytes_to_mebibytes,
    memory_percent_used,
)
from hardware.operations import create_device_id
from hardware.vendors.intel.capability_parsing import extract_intel_dump_devices
from hardware.vendors.intel.commands import (
    IntelReadError,
    execute_intel_dump_json,
    resolve_intel_read_dialect,
)
from hardware.vendors.intel.physical_binding import (
    IntelDiscoveryObservations,
    acquire_intel_discovery_observations,
)
from hardware.vendors.intel.runtime import is_xpu_smi_available

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("query_intel_gpus",)

LOGGER_NAME = "SoAI.hardware.vendors.intel_gpu_info"
OPERATION = "hardware_intel.query_intel_gpus"
INTEL_OPTIONAL_READ_FAILURES: tuple[type[Exception], ...] = (
    StateError,
    *RECOVERABLE_EXCEPTIONS,
)


def query_intel_gpus(
    executor: CommandExecutorProtocol,
    detailed: bool,
) -> tuple[list[JSONDict], JSONDict]:
    intel_logger = get_logger(LOGGER_NAME)
    if not is_xpu_smi_available():
        return ([], {})
    gpus: list[JSONDict] = []
    drivers: JSONDict = {}
    failure: Exception | None = None
    malformed_response = False
    try:
        dialect = resolve_intel_read_dialect(executor)
        if dialect.protocol == "metrics":
            discovery = acquire_intel_discovery_observations(
                executor, executable=dialect.executable
            )
            gpus.extend(_discovery_candidates(discovery))
        payload = execute_intel_dump_json(executor, dialect=dialect)
        devices = extract_intel_dump_devices(payload)
        for device_index, device_value in enumerate(devices):
            _append_intel_gpu_entry(gpus, device_index, device_value, detailed, intel_logger)
        if isinstance(payload, dict) and "level_zero_version" in payload:
            drivers["Level Zero"] = {
                "version": payload["level_zero_version"],
                "driver_version": payload.get("driver_version"),
            }
    except IntelReadError as exception:
        failure = exception
        for gpu in gpus:
            if gpu.get("telemetry_unavailable_reason") == "unsupported_protocol":
                gpu["telemetry_unavailable_reason"] = exception.state.value
    except INTEL_OPTIONAL_READ_FAILURES as exception:
        failure = exception
    except ValidationError as exception:
        failure = exception
        malformed_response = True
    if failure is not None:
        if malformed_response:
            log_exception(
                intel_logger,
                failure,
                message="Failed to parse xpu-smi output",
                operation=OPERATION,
            )
        else:
            log_handled_exception(
                intel_logger,
                failure,
                message="xpu-smi GPU inventory query failed (non-critical).",
                operation=OPERATION,
                level="warning",
            )
    return (gpus, drivers)


def _discovery_candidates(discovery: IntelDiscoveryObservations) -> list[JSONDict]:
    gpus: list[JSONDict] = []
    for device in discovery.devices:
        identity = device.identity
        if identity is None:
            continue
        locator = identity.uuid if identity.uuid is not None else identity.pci_bdf_full
        if locator is None:
            continue
        entry = build_gpu_entry(
            vendor="intel",
            index=len(gpus),
            vendor_id=device.native_device_id,
            device_id=create_device_id("gpu", f"intel-{locator}"),
            name="Intel GPU",
            memory_used_mb=0,
            memory_total_mb=0,
            percent_used=0.0,
        )
        entry.update(
            {
                "memory_total_mb": None,
                "memory_used_mb": None,
                "percent_used": None,
                "gpu_uuid_observations": [identity.uuid] if identity.uuid is not None else [],
                "pci_bdf_observations": list(device.pci_bdf_observations),
                "pci_bdf_full": identity.pci_bdf_full,
                "compute_capable": True,
                "telemetry_available": False,
                "telemetry_unavailable_reason": (
                    "device_recovery_required"
                    if device.device_state is not None or device.recovery_action is not None
                    else "unsupported_protocol"
                ),
            }
        )
        if identity.uuid is not None:
            entry["gpu_uuid"] = identity.uuid
        gpus.append(entry)
    return gpus


def _append_intel_gpu_entry(
    gpus: list[JSONDict],
    device_index: int,
    device: JSONDict,
    detailed: bool,
    intel_logger: LoggerProtocol,
) -> None:
    total_mem = coerce_non_negative_exact_int_or_none(device.get("memory_physical_size"))
    used_mem = coerce_non_negative_exact_int_or_none(device.get("memory_used"))
    core_clock = next(
        (
            value
            for field in ("frequency_current", "core_frequency", "compute_frequency")
            if (value := coerce_float_from_text(device.get(field))) is not None and value >= 0
        ),
        None,
    )
    mem_clock = next(
        (
            value
            for field in ("memory_frequency", "dram_frequency")
            if (value := coerce_float_from_text(device.get(field))) is not None and value >= 0
        ),
        None,
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
        memory_used_mb=bytes_to_mebibytes(used_mem) if used_mem is not None else None,
        memory_total_mb=bytes_to_mebibytes(total_mem) if total_mem is not None else None,
        percent_used=(
            memory_percent_used(used_mem, total_mem)
            if total_mem is not None
            and used_mem is not None
            and 0 <= used_mem <= total_mem
            and total_mem > 0
            else None
        ),
        temperature=coerce_float_from_text(device.get("ras_gpu_temperature")),
        utilization=coerce_float_from_text(device.get("ras_gpu_utilization")),
        power_draw_watts=coerce_float_from_text(device.get("power")),
        power_limit_watts=coerce_float_from_text(device.get("power_limit")),
        processes=(
            [{"pid": pid, "name": "N/A", "used_memory_mb": 0} for pid in pids] if detailed else []
        ),
    )
    gpu_entry["gpu_uuid"] = primary_device_id
    actual_uuid = device.get("uuid")
    gpu_entry["gpu_uuid_observations"] = [actual_uuid] if actual_uuid is not None else []
    actual_pci = device.get("pci_bdf_address")
    gpu_entry["pci_bdf_observations"] = [actual_pci] if actual_pci is not None else []
    if isinstance(actual_pci, str) and normalize_observed_full_pci_bdf(actual_pci):
        gpu_entry["pci_bdf_full"] = actual_pci
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
