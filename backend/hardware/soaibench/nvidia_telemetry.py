"""SoAI - SoAIBench NVIDIA fast telemetry reader [backend/hardware/soaibench/nvidia_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes

from core.errors.exceptions import StateError
from core.hardware.protocols import NvmlGateProtocol
from core.types.json import JSONDict
from hardware.soaibench.internal_protocols import (
    NvidiaClockEventNvmlModuleProtocol,
    NvidiaPowerNvmlModuleProtocol,
    NvidiaTelemetryNvmlModuleProtocol,
    NvidiaTemperatureNvmlModuleProtocol,
    NvidiaThrottleNvmlModuleProtocol,
    NvidiaUtilizationNvmlModuleProtocol,
)
from hardware.vendors.nvidia.nvml_metric_reading import (
    is_nvml_error_not_supported,
    pynvml_module_ref,
)

__all__ = ("read_nvidia_fast_telemetry",)

PROVIDER_DIAGNOSTIC = "nvidia_telemetry_provider_unavailable"


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
    try:
        with nvml_gate.session():
            device_count = int(active_pynvml_module.nvmlDeviceGetCount())
            for device_index in range(device_count):
                handle = active_pynvml_module.nvmlDeviceGetHandleByIndex(device_index)
                if not _handle_matches_pci_bdf(active_pynvml_module, handle, pci_bdf):
                    continue
                return _read_handle_telemetry(active_pynvml_module, handle)
    except (active_pynvml_module.NVMLError, StateError):
        return {"diagnostic_code": PROVIDER_DIAGNOSTIC}
    return None


def _read_handle_telemetry(
    pynvml_module: NvidiaTelemetryNvmlModuleProtocol,
    handle: ctypes.c_void_p,
) -> JSONDict:
    telemetry: JSONDict = {}
    temperature, temperature_failed = _read_temperature(pynvml_module, handle)
    power, power_failed = _read_power(pynvml_module, handle)
    utilization, utilization_failed = _read_utilization(pynvml_module, handle)
    throttle_detected, throttle_failed = _read_throttle(pynvml_module, handle)
    if temperature is not None:
        telemetry["temperature_celsius"] = float(temperature)
    if power is not None:
        telemetry["avg_power_watts"] = power
        telemetry["max_power_watts"] = power
        telemetry["power_draw_watts"] = power
    if utilization is not None:
        telemetry["core_utilization_percent"] = float(utilization)
    if throttle_detected is not None:
        telemetry["throttle_detected"] = throttle_detected
    if temperature_failed or power_failed or utilization_failed or throttle_failed:
        telemetry["diagnostic_code"] = PROVIDER_DIAGNOSTIC
    return telemetry


def _read_temperature(
    pynvml_module: NvidiaTelemetryNvmlModuleProtocol,
    handle: ctypes.c_void_p,
) -> tuple[float | None, bool]:
    if not isinstance(pynvml_module, NvidiaTemperatureNvmlModuleProtocol):
        return None, False
    try:
        value = pynvml_module.nvmlDeviceGetTemperature(
            handle,
            pynvml_module.NVML_TEMPERATURE_GPU,
        )
    except pynvml_module.NVMLError as exception:
        return None, not is_nvml_error_not_supported(exception)
    return float(value), False


def _read_power(
    pynvml_module: NvidiaTelemetryNvmlModuleProtocol,
    handle: ctypes.c_void_p,
) -> tuple[float | None, bool]:
    if not isinstance(pynvml_module, NvidiaPowerNvmlModuleProtocol):
        return None, False
    try:
        value = pynvml_module.nvmlDeviceGetPowerUsage(handle)
    except pynvml_module.NVMLError as exception:
        return None, not is_nvml_error_not_supported(exception)
    return float(value) / 1000.0, False


def _read_utilization(
    pynvml_module: NvidiaTelemetryNvmlModuleProtocol,
    handle: ctypes.c_void_p,
) -> tuple[float | None, bool]:
    if not isinstance(pynvml_module, NvidiaUtilizationNvmlModuleProtocol):
        return None, False
    try:
        value = pynvml_module.nvmlDeviceGetUtilizationRates(handle)
    except pynvml_module.NVMLError as exception:
        return None, not is_nvml_error_not_supported(exception)
    return float(value.gpu), False


def _read_throttle(
    pynvml_module: NvidiaTelemetryNvmlModuleProtocol,
    handle: ctypes.c_void_p,
) -> tuple[bool | None, bool]:
    if isinstance(pynvml_module, NvidiaClockEventNvmlModuleProtocol):
        try:
            reasons = pynvml_module.nvmlDeviceGetCurrentClocksEventReasons(handle)
        except pynvml_module.NVMLError as exception:
            if not is_nvml_error_not_supported(exception):
                return None, True
        else:
            return reasons != pynvml_module.nvmlClocksEventReasonNone, False
    if isinstance(pynvml_module, NvidiaThrottleNvmlModuleProtocol):
        try:
            reasons = pynvml_module.nvmlDeviceGetCurrentClocksThrottleReasons(handle)
        except pynvml_module.NVMLError as exception:
            return None, not is_nvml_error_not_supported(exception)
        return reasons != pynvml_module.nvmlClocksThrottleReasonNone, False
    return None, False


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
