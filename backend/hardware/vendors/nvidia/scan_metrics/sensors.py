"""SoAI - NVIDIA scan sensor metric readers [backend/hardware/vendors/nvidia/scan_metrics/sensors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable

import pynvml

from core.logging.protocols import TraceLogger
from hardware.vendors.nvidia.nvml_metric_reading import read_nvidia_metric_value

__all__ = (
    "read_core_clock_mhz",
    "read_mem_clock_mhz",
    "read_power_draw_watts",
    "read_power_limit_watts",
    "read_temperature",
    "read_utilization",
)


def _read_int_metric(
    *,
    reader: Callable[[], int | None],
    metric_name: str,
    device_index: int,
    logger: TraceLogger,
) -> int | None:
    value = read_nvidia_metric_value(reader, metric_name, device_index, logger=logger)
    return int(value) if value is not None else None


def read_temperature(
    device_index: int,
    handle: ctypes.c_void_p,
    *,
    logger: TraceLogger,
) -> int | None:
    try:
        device_get_temperature = pynvml.nvmlDeviceGetTemperature
    except AttributeError:
        device_get_temperature = None
    try:
        temperature_gpu = pynvml.NVML_TEMPERATURE_GPU
    except AttributeError:
        temperature_gpu = None
    if not callable(device_get_temperature) or not isinstance(temperature_gpu, int):
        return None

    def read_temperature_metric() -> int:
        return device_get_temperature(handle, temperature_gpu)

    return _read_int_metric(
        reader=read_temperature_metric,
        metric_name="temperature",
        device_index=device_index,
        logger=logger,
    )


def read_utilization(
    device_index: int,
    handle: ctypes.c_void_p,
    *,
    logger: TraceLogger,
) -> int | None:
    try:
        device_get_utilization_rates = pynvml.nvmlDeviceGetUtilizationRates
    except AttributeError:
        device_get_utilization_rates = None
    if not callable(device_get_utilization_rates):
        return None

    def read_utilization_metric() -> int | None:
        utilization_entry = device_get_utilization_rates(handle)
        try:
            gpu_utilization = utilization_entry.gpu
        except AttributeError:
            return None
        return int(gpu_utilization) if isinstance(gpu_utilization, int) else None

    return _read_int_metric(
        reader=read_utilization_metric,
        metric_name="utilization",
        device_index=device_index,
        logger=logger,
    )


def read_power_draw_watts(
    device_index: int,
    handle: ctypes.c_void_p,
    *,
    logger: TraceLogger,
) -> float | None:
    try:
        device_get_power_usage = pynvml.nvmlDeviceGetPowerUsage
    except AttributeError:
        device_get_power_usage = None
    if not callable(device_get_power_usage):
        return None

    def read_power_metric() -> int:
        power_usage_milliwatts = device_get_power_usage(handle)
        return int(power_usage_milliwatts)

    raw_power_usage = read_nvidia_metric_value(
        read_power_metric,
        "power_draw_watts",
        device_index,
        logger=logger,
    )
    return (raw_power_usage / 1000.0) if raw_power_usage is not None else None


def read_power_limit_watts(
    device_index: int,
    handle: ctypes.c_void_p,
    *,
    logger: TraceLogger,
) -> float | None:
    try:
        device_get_power_limit = pynvml.nvmlDeviceGetPowerManagementLimit
    except AttributeError:
        device_get_power_limit = None
    if not callable(device_get_power_limit):
        return None

    def read_power_limit_metric() -> int:
        power_limit_milliwatts = device_get_power_limit(handle)
        return int(power_limit_milliwatts)

    raw_power_limit = read_nvidia_metric_value(
        read_power_limit_metric,
        "power_limit_watts",
        device_index,
        logger=logger,
    )
    return (raw_power_limit / 1000.0) if raw_power_limit is not None else None


def _read_clock(
    *,
    handle: ctypes.c_void_p,
    device_index: int,
    logger: TraceLogger,
    clock_type: int,
    metric_name: str,
) -> int | None:
    try:
        device_get_clock = pynvml.nvmlDeviceGetClock
    except AttributeError:
        device_get_clock = None
    if not callable(device_get_clock):
        return None

    def read_clock_metric() -> int:
        return device_get_clock(handle, clock_type, 0)

    return _read_int_metric(
        reader=read_clock_metric,
        metric_name=metric_name,
        device_index=device_index,
        logger=logger,
    )


def read_core_clock_mhz(
    device_index: int,
    handle: ctypes.c_void_p,
    *,
    logger: TraceLogger,
) -> int | None:
    try:
        clock_graphics = pynvml.NVML_CLOCK_GRAPHICS
    except AttributeError:
        clock_graphics = None
    if not isinstance(clock_graphics, int):
        return None
    return _read_clock(
        handle=handle,
        device_index=device_index,
        logger=logger,
        clock_type=clock_graphics,
        metric_name="core_clock_mhz",
    )


def read_mem_clock_mhz(
    device_index: int,
    handle: ctypes.c_void_p,
    *,
    logger: TraceLogger,
) -> int | None:
    try:
        clock_mem = pynvml.NVML_CLOCK_MEM
    except AttributeError:
        clock_mem = None
    if not isinstance(clock_mem, int):
        return None
    return _read_clock(
        handle=handle,
        device_index=device_index,
        logger=logger,
        clock_type=clock_mem,
        metric_name="mem_clock_mhz",
    )
