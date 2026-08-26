"""SoAI - Windows CPU inventory collection [backend/hardware/windows_cpu_info.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import platform
import re
from typing import TYPE_CHECKING

import psutil

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.serialization.json_parsing import parse_json_value
from core.types.json_value import filter_json_dict_list
from core.validation.numbers import coerce_int_from_json
from core.validation.strings import coerce_optional_trimmed_str
from hardware.operations import create_device_id
from hardware.probe_failure_logging import execute_hardware_probe_command
from hardware.windows_commands import build_windows_powershell_command

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "get_windows_cpu_info",
    "sanitize_cpu_display_name",
)

LOGGER_NAME = "SoAI.hardware.windows_cpu_info"
OPERATION_HARDWARE_WINDOWS_CPU_INFO_QUERY = "hardware.windows_cpu_info.query"
OPERATION_HARDWARE_WINDOWS_CPU_REGISTRY_QUERY = "hardware.windows_cpu_info.registry_query"
WINDOWS_CPU_QUERY = (
    "Get-CimInstance -ClassName Win32_Processor | "
    "Select-Object Name,Manufacturer,Architecture,NumberOfCores,"
    "NumberOfLogicalProcessors,MaxClockSpeed,CurrentClockSpeed,L3CacheSize,"
    "SocketDesignation,DeviceID | ConvertTo-Json -Compress"
)
WINDOWS_CPU_NAME_REGISTRY_QUERY = (
    "Get-ItemPropertyValue -Path "
    "'HKLM:\\HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0' "
    "-Name ProcessorNameString"
)
_CPU_SIGNATURE_PATTERN = r"\bfamily\s+\d+\b.*\bmodel\s+\d+\b.*\bstepping\s+\d+\b"


def sanitize_cpu_display_name(value: JSONValue) -> str | None:
    name = coerce_optional_trimmed_str(value)
    if name is None:
        return None
    normalized = " ".join(name.split())
    if re.search(_CPU_SIGNATURE_PATTERN, normalized, flags=re.IGNORECASE):
        return None
    if normalized.lower() in {"unknown", "none", "null"}:
        return None
    return normalized


def get_windows_cpu_info(executor: CommandExecutorProtocol) -> list[JSONDict]:
    result = execute_hardware_probe_command(
        executor,
        build_windows_powershell_command(WINDOWS_CPU_QUERY),
        logger=get_logger(LOGGER_NAME),
        message="Failed to query Windows CPU inventory.",
        operation=OPERATION_HARDWARE_WINDOWS_CPU_INFO_QUERY,
        timeout=10,
    )
    if result is None:
        return []
    if result.return_code != 0 or not result.stdout.strip():
        return []
    try:
        parsed = parse_json_value(result.stdout, field="Win32_Processor output")
    except ValidationError as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to parse Windows CPU inventory output.",
            operation=OPERATION_HARDWARE_WINDOWS_CPU_INFO_QUERY,
            level="trace",
        )
        return []
    records = filter_json_dict_list(parsed if isinstance(parsed, list) else [parsed])
    if not records:
        return []
    registry_name = _read_registry_processor_name(executor)
    cpu_info: list[JSONDict] = []
    for socket_index, record in enumerate(records):
        cpu_info.append(_build_windows_cpu_entry(record, socket_index, registry_name))
    return cpu_info


def _build_windows_cpu_entry(
    record: JSONDict,
    socket_index: int,
    registry_name: str | None,
) -> JSONDict:
    physical_cores = _coerce_positive_int(record.get("NumberOfCores"))
    logical_cores = _coerce_positive_int(record.get("NumberOfLogicalProcessors"))
    fallback_physical = psutil.cpu_count(logical=False)
    fallback_logical = psutil.cpu_count(logical=True)
    return {
        "device_id": create_device_id("cpu", socket_index),
        "socket_id": socket_index,
        "name": sanitize_cpu_display_name(record.get("Name")) or registry_name or "Unknown CPU",
        "architecture": _windows_architecture_name(record.get("Architecture")),
        "physical_cores": physical_cores if physical_cores is not None else fallback_physical,
        "logical_cores": logical_cores if logical_cores is not None else fallback_logical,
        "min_freq_mhz": None,
        "max_freq_mhz": _coerce_nonnegative_int(record.get("MaxClockSpeed")),
        "current_freq_mhz": _coerce_nonnegative_int(record.get("CurrentClockSpeed")),
        "l3_cache_kb": _coerce_nonnegative_int(record.get("L3CacheSize")),
        "usage_percent": 0.0,
        "temperature_celsius": None,
        "power_draw_watts": None,
    }


def _read_registry_processor_name(executor: CommandExecutorProtocol) -> str | None:
    result = execute_hardware_probe_command(
        executor,
        build_windows_powershell_command(WINDOWS_CPU_NAME_REGISTRY_QUERY),
        logger=get_logger(LOGGER_NAME),
        message="Failed to read Windows processor registry name.",
        operation=OPERATION_HARDWARE_WINDOWS_CPU_REGISTRY_QUERY,
        timeout=5,
    )
    if result is None:
        return None
    if result.return_code != 0:
        return None
    return sanitize_cpu_display_name(result.stdout)


def _coerce_nonnegative_int(value: JSONValue) -> int | None:
    parsed = coerce_int_from_json(value, default=None, allow_bool=False)
    if parsed is None or parsed < 0:
        return None
    return parsed


def _coerce_positive_int(value: JSONValue) -> int | None:
    parsed = _coerce_nonnegative_int(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _windows_architecture_name(value: JSONValue) -> str:
    architecture = coerce_int_from_json(value, default=None, allow_bool=False)
    if architecture == 9:
        return "x86_64"
    if architecture == 12:
        return "arm64"
    if architecture == 0:
        return "x86"
    return platform.machine()
