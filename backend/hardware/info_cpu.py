"""SoAI - CPU hardware information collection and monitoring [backend/hardware/info_cpu.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import platform
import shutil
from typing import TYPE_CHECKING

import psutil

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.open_files import open_text
from core.hardware.device_display_name import build_device_display_name
from core.logging.trace import get_logger
from core.runtime.platform import get_runtime_platform
from core.serialization.json_parsing import parse_json_dict
from core.validation.text_numbers import coerce_float_from_text
from hardware.cpu_rapl import RaplEnergyCache, sample_rapl_cpu_power
from hardware.operations import create_device_id
from hardware.windows_cpu_info import get_windows_cpu_info, sanitize_cpu_display_name

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("get_cpu_info",)

LOGGER_NAME = "SoAI.hardware.info_cpu"
OPERATION_HARDWARE_INFO_CPU_FIND_HWMON_PATH = "hardware_info.cpu.find_hwmon_path"
OPERATION_HARDWARE_INFO_CPU_GET_CPU_INFO_CPU_FREQ = "hardware_info.cpu.get_cpu_info.cpu_freq"
OPERATION_HARDWARE_INFO_CPU_GET_CPU_INFO_TEMPERATURE = "hardware_info.cpu.get_cpu_info.temperature"
OPERATION_HARDWARE_INFO_GET_CPU_INFO = "hardware_info.get_cpu_info"
LSCPU_PARSE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ValidationError,
    *RECOVERABLE_EXCEPTIONS,
)
HWMON_SENSOR_EXCEPTIONS: tuple[type[Exception], ...] = (
    OSError,
    *RECOVERABLE_EXCEPTIONS,
)


def _find_hwmon_path() -> str | None:
    logger = get_logger(LOGGER_NAME)
    base = "/sys/class/hwmon"
    if not os.path.exists(base):
        return None
    try:
        entries = os.listdir(base)
    except OSError:
        return None
    for name in entries:
        hwmon_path = os.path.join(base, name)
        if not os.path.isdir(hwmon_path):
            continue
        try:
            with open_text(
                os.path.join(hwmon_path, "name"),
                encoding="utf-8",
            ) as file_handle:
                if "coretemp" in file_handle.read().lower():
                    return hwmon_path
        except HWMON_SENSOR_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to inspect hwmon entry while detecting CPU sensors (non-critical).",
                operation=OPERATION_HARDWARE_INFO_CPU_FIND_HWMON_PATH,
                details={"hwmon_path": hwmon_path},
                level="trace",
            )
            continue
    return None


def _apply_rapl_power(cpu_info: list[JSONDict], rapl_energy_cache: RaplEnergyCache) -> None:
    sample = sample_rapl_cpu_power(rapl_energy_cache)
    if not sample.packages:
        return
    readings_by_socket = {reading.socket_index: reading for reading in sample.packages}
    for cpu in cpu_info:
        socket_id = cpu.get("socket_id")
        reading = readings_by_socket.get(socket_id) if isinstance(socket_id, int) else None
        if reading is None:
            continue
        if reading.power_draw_watts is not None:
            cpu["power_draw_watts"] = reading.power_draw_watts
        if reading.power_limit_watts is not None:
            cpu["power_limit_watts"] = reading.power_limit_watts


def get_cpu_info(
    executor: CommandExecutorProtocol,
    *,
    rapl_energy_cache: RaplEnergyCache,
) -> list[JSONDict]:
    logger = get_logger(LOGGER_NAME)
    cpu_info: list[JSONDict] = []
    runtime_platform = get_runtime_platform()
    if runtime_platform.is_linux:
        lscpu_path = shutil.which("lscpu")
        if lscpu_path:
            result = executor.execute(
                [lscpu_path, "--json"],
                timeout=10,
                shell=False,
                use_sudo=False,
            )
            stdout = result.stdout
            if stdout:
                try:
                    lscpu_data = parse_json_dict(stdout, field="lscpu output")
                    cpu_map: dict[str, str] = {}
                    entries_value = lscpu_data.get("lscpu")
                    if isinstance(entries_value, list):
                        for entry_value in entries_value:
                            if not isinstance(entry_value, dict):
                                continue
                            field_value = entry_value.get("field")
                            field = field_value.strip(":") if isinstance(field_value, str) else ""
                            data_value = entry_value.get("data")
                            data = (
                                data_value if isinstance(data_value, str) else str(data_value or "")
                            )
                            if field:
                                cpu_map[field] = data
                    sockets = int(cpu_map.get("Socket(s)", 1))
                    cores_per_socket = int(cpu_map.get("Core(s) per socket", 1))
                    threads_per_core = int(cpu_map.get("Thread(s) per core", 1))
                    for socket_index in range(sockets):
                        socket_info: JSONDict = {
                            "device_id": create_device_id("cpu", socket_index),
                            "socket_id": socket_index,
                            "name": cpu_map.get("Model name")
                            or sanitize_cpu_display_name(platform.processor())
                            or "Unknown CPU",
                            "architecture": cpu_map.get(
                                "Architecture",
                                platform.machine(),
                            ),
                            "physical_cores": cores_per_socket,
                            "logical_cores": cores_per_socket * threads_per_core,
                            "min_freq_mhz": (
                                coerce_float_from_text(cpu_map.get("CPU min MHz"))
                                if cpu_map.get("CPU min MHz")
                                else None
                            ),
                            "max_freq_mhz": (
                                coerce_float_from_text(cpu_map.get("CPU max MHz"))
                                if cpu_map.get("CPU max MHz")
                                else None
                            ),
                            "current_freq_mhz": None,
                            "l3_cache_kb": None,
                            "usage_percent": 0.0,
                            "temperature_celsius": None,
                            "power_draw_watts": None,
                        }
                        cpu_info.append(socket_info)
                except LSCPU_PARSE_EXCEPTIONS as exception:
                    log_exception(
                        logger,
                        exception,
                        message="Failed to parse lscpu output",
                        operation=OPERATION_HARDWARE_INFO_GET_CPU_INFO,
                    )
    elif runtime_platform.is_windows:
        cpu_info = get_windows_cpu_info(executor)
    if not cpu_info:
        try:
            cpu_freq = psutil.cpu_freq()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to query CPU frequency (non-critical).",
                operation=OPERATION_HARDWARE_INFO_CPU_GET_CPU_INFO_CPU_FREQ,
                level="trace",
            )
            cpu_freq = None
        cpu_info = [
            {
                "device_id": create_device_id("cpu", 0),
                "socket_id": 0,
                "name": sanitize_cpu_display_name(platform.processor()) or "Unknown CPU",
                "architecture": platform.machine(),
                "physical_cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
                "min_freq_mhz": cpu_freq.min if cpu_freq else None,
                "max_freq_mhz": cpu_freq.max if cpu_freq else None,
                "current_freq_mhz": cpu_freq.current if cpu_freq else None,
                "l3_cache_kb": None,
                "usage_percent": 0.0,
                "temperature_celsius": None,
                "power_draw_watts": None,
            },
        ]
    hwmon_path = _find_hwmon_path()
    if hwmon_path:
        try:
            filenames = os.listdir(hwmon_path)
        except OSError:
            filenames = []
        for filename in filenames:
            if filename.startswith("temp") and filename.endswith("_input"):
                temp_file = os.path.join(hwmon_path, filename)
                try:
                    with open_text(temp_file, encoding="utf-8") as file_handle:
                        temp_value = float(file_handle.read().strip()) / 1000
                    for cpu in cpu_info:
                        cpu["temperature_celsius"] = temp_value
                except HWMON_SENSOR_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Failed to read CPU temperature sensor value (non-critical).",
                        operation=OPERATION_HARDWARE_INFO_CPU_GET_CPU_INFO_TEMPERATURE,
                        details={"temp_file": temp_file},
                        level="trace",
                    )
                    continue
    _apply_rapl_power(cpu_info, rapl_energy_cache)
    if cpu_info:
        overall_usage = psutil.cpu_percent(interval=None)
        for cpu in cpu_info:
            cpu["usage_percent"] = overall_usage
            cpu["display_name"] = build_device_display_name(cpu.get("name"))
    return cpu_info
