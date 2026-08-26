"""SoAI - SoAIBench NVIDIA fast telemetry reader [backend/hardware/soaibench/nvidia_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.protocols import NvmlGateProtocol
from core.logging.trace import get_logger
from core.types.json import JSONDict
from hardware.soaibench.internal_protocols import NvidiaTelemetryNvmlModuleProtocol
from hardware.vendors.nvidia.nvml_metric_reading import pynvml_module_ref
from hardware.vendors.nvidia.scan_metrics.sensors import (
    read_power_draw_watts,
    read_temperature,
    read_utilization,
)

__all__ = ("read_nvidia_fast_telemetry",)

LOGGER_NAME = "SoAI.hardware.soaibench.nvidia_telemetry"
OPERATION = "hardware.soaibench.nvidia_telemetry.read"


def read_nvidia_fast_telemetry(
    device_id: str,
    *,
    nvml_gate: NvmlGateProtocol,
) -> JSONDict | None:
    if not nvml_gate.nvml_available:
        return None
    pci_bdf = _device_id_pci_bdf(device_id)
    if pci_bdf is None:
        return None
    active_pynvml_module = pynvml_module_ref
    if not isinstance(active_pynvml_module, NvidiaTelemetryNvmlModuleProtocol):
        return None
    logger = get_logger(LOGGER_NAME)
    try:
        with nvml_gate.session():
            device_count = int(active_pynvml_module.nvmlDeviceGetCount())
            for device_index in range(device_count):
                handle = active_pynvml_module.nvmlDeviceGetHandleByIndex(device_index)
                if not _handle_matches_pci_bdf(active_pynvml_module, handle, pci_bdf):
                    continue
                return _read_handle_telemetry(device_index, handle)
    except active_pynvml_module.NVMLError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read NVIDIA fast SoAIBench telemetry (non-critical).",
            operation=OPERATION,
            level="trace",
            details={"device_id": device_id},
        )
    except StateError as exception:
        log_handled_exception(
            logger,
            exception,
            message="NVML is unavailable for fast SoAIBench telemetry (non-critical).",
            operation=OPERATION,
            level="trace",
            details={"device_id": device_id},
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read NVIDIA fast SoAIBench telemetry (non-critical).",
            operation=OPERATION,
            level="trace",
            details={"device_id": device_id},
        )
    return None


def _read_handle_telemetry(device_index: int, handle: ctypes.c_void_p) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    telemetry: JSONDict = {}
    temperature = read_temperature(device_index, handle, logger=logger)
    power = read_power_draw_watts(device_index, handle, logger=logger)
    utilization = read_utilization(device_index, handle, logger=logger)
    if temperature is not None:
        telemetry["temperature_celsius"] = float(temperature)
    if power is not None:
        telemetry["avg_power_watts"] = power
        telemetry["max_power_watts"] = power
        telemetry["power_draw_watts"] = power
    if utilization is not None:
        telemetry["core_utilization_percent"] = float(utilization)
    return telemetry


def _handle_matches_pci_bdf(
    pynvml_module: NvidiaTelemetryNvmlModuleProtocol,
    handle: ctypes.c_void_p,
    pci_bdf: str,
) -> bool:
    pci_info = pynvml_module.nvmlDeviceGetPciInfo(handle)
    bus_id = pci_info.busId
    bus_text = bus_id.decode() if isinstance(bus_id, bytes) else str(bus_id)
    return _normalize_pci_bdf(bus_text).endswith(_normalize_pci_bdf(pci_bdf))


def _device_id_pci_bdf(device_id: str) -> str | None:
    prefix = "gpu:nvidia-pci-"
    if not device_id.startswith(prefix):
        return None
    pci_bdf = device_id.removeprefix(prefix).strip()
    return pci_bdf if pci_bdf else None


def _normalize_pci_bdf(value: str) -> str:
    normalized = value.strip().lower()
    if normalized.startswith("00000000:"):
        return normalized.removeprefix("00000000:")
    if normalized.startswith("0000:"):
        return normalized.removeprefix("0000:")
    return normalized
