"""SoAI - CPU hardware information collection and monitoring [backend/hardware/info_cpu.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import platform
import shutil
from copy import deepcopy
from typing import TYPE_CHECKING

import psutil

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.device_display_name import build_device_display_name
from core.logging.trace import get_logger
from core.runtime.platform import get_runtime_platform
from core.serialization.json_parsing import parse_json_dict
from core.validation.numbers import coerce_int_from_json
from hardware.cpu_inventory.darwin_metadata import read_darwin_cpu_metadata
from hardware.cpu_inventory.linux_topology import (
    parse_linux_cpu_topology,
    read_online_core_relationships,
)
from hardware.cpu_inventory.thermal_sensors import read_cpu_temperatures
from hardware.cpu_inventory.topology_totals import kernel_package_counts
from hardware.cpu_rapl import RaplEnergyCache, sample_rapl_cpu_power
from hardware.operations import create_device_id
from hardware.windows_cpu_info import get_windows_cpu_info, sanitize_cpu_display_name

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("get_cpu_info",)

LOGGER_NAME = "SoAI.hardware.info_cpu"
OPERATION_HARDWARE_INFO_CPU_GET_CPU_INFO_CPU_FREQ = "hardware_info.cpu.get_cpu_info.cpu_freq"
OPERATION_HARDWARE_INFO_GET_CPU_INFO = "hardware_info.get_cpu_info"
LSCPU_PARSE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ValidationError,
    *RECOVERABLE_EXCEPTIONS,
)


def _apply_rapl_power(cpu_info: list[JSONDict], rapl_energy_cache: RaplEnergyCache) -> None:
    sample = sample_rapl_cpu_power(rapl_energy_cache)
    if not sample.packages:
        return
    readings_by_socket = {reading.socket_index: reading for reading in sample.packages}
    for cpu in cpu_info:
        socket_id = cpu.get("socket_id")
        reading = (
            readings_by_socket.get(socket_id)
            if isinstance(socket_id, int) and not isinstance(socket_id, bool)
            else None
        )
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
    windows_inventory: list[JSONDict] | None = None,
) -> list[JSONDict]:
    logger = get_logger(LOGGER_NAME)
    cpu_info: list[JSONDict] = []
    runtime_platform = get_runtime_platform()
    if runtime_platform.is_linux:
        lscpu_path = shutil.which("lscpu")
        if lscpu_path:
            result = executor.execute(
                ["env", "LC_ALL=C", lscpu_path, "--json"],
                timeout=10,
                shell=False,
                use_sudo=False,
            )
            stdout = result.stdout
            if stdout and result.return_code == 0:
                try:
                    lscpu_data = parse_json_dict(stdout, field="lscpu output")
                    cpu_info = parse_linux_cpu_topology(lscpu_data)
                    for socket_index, cpu in enumerate(cpu_info):
                        cpu["device_id"] = create_device_id("cpu", socket_index)
                        cpu["name"] = (
                            cpu.get("name")
                            or sanitize_cpu_display_name(platform.processor())
                            or "Unknown CPU"
                        )
                        cpu["architecture"] = cpu.get("architecture") or platform.machine()
                        cpu.update(
                            {
                                "current_freq_mhz": None,
                                "l3_cache_kb": None,
                                "usage_percent": 0.0,
                                "temperature_celsius": None,
                                "power_draw_watts": None,
                            }
                        )
                        if cpu.get("topology_scope") == "aggregate":
                            online_ids = cpu.get("online_cpu_ids")
                            relationships = (
                                read_online_core_relationships(
                                    [
                                        identity
                                        for identity in online_ids
                                        if isinstance(identity, int)
                                        and not isinstance(identity, bool)
                                    ],
                                    coerce_int_from_json(cpu.get("reported_logical_cores")),
                                )
                                if isinstance(online_ids, list)
                                else {"relationship_status": "unavailable"}
                            )
                            cpu.update(relationships)
                            physical_count = coerce_int_from_json(psutil.cpu_count(logical=False))
                            logical_count = coerce_int_from_json(psutil.cpu_count(logical=True))
                            if (
                                cpu.get("logical_cores") is None
                                and logical_count is not None
                                and logical_count > 0
                            ):
                                cpu["logical_cores"] = logical_count
                                cpu["logical_count_source"] = "psutil"
                            if relationships.get("relationship_status") in (
                                "conflict",
                                "incomplete",
                            ):
                                cpu["physical_cores"] = None
                                cpu["topology_status"] = relationships.get("relationship_status")
                            elif (
                                relationships.get("relationship_status") == "available"
                                and relationships.get("relationship_scope") == "present"
                            ):
                                cpu["physical_cores"] = relationships.get("online_physical_cores")
                                cpu["physical_count_source"] = "online_core_relationships"
                            elif (
                                physical_count is not None
                                and logical_count is not None
                                and 0 < physical_count <= logical_count
                                and logical_count == cpu.get("logical_cores")
                            ):
                                cpu["physical_cores"] = physical_count
                                cpu["physical_count_source"] = "psutil"
                            else:
                                cpu["physical_cores"] = None

                except LSCPU_PARSE_EXCEPTIONS as exception:
                    log_exception(
                        logger,
                        exception,
                        message="Failed to parse lscpu output",
                        operation=OPERATION_HARDWARE_INFO_GET_CPU_INFO,
                    )
    elif runtime_platform.is_windows:
        cpu_info = (
            get_windows_cpu_info(executor)
            if windows_inventory is None
            else deepcopy(windows_inventory)
        )
        if windows_inventory is not None:
            try:
                current_frequency = psutil.cpu_freq()
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to query CPU frequency (non-critical).",
                    operation=OPERATION_HARDWARE_INFO_CPU_GET_CPU_INFO_CPU_FREQ,
                    level="trace",
                )
                current_frequency = None
            for cpu in cpu_info:
                cpu["current_freq_mhz"] = (
                    current_frequency.current if current_frequency is not None else None
                )
    if not cpu_info:
        try:
            cpu_freq = None if runtime_platform.is_macos else psutil.cpu_freq()
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
                "socket_id": None,
                "topology_scope": "aggregate",
                "topology_status": "fallback",
                "physical_count_source": "psutil",
                "logical_count_source": "psutil",
                "name": (
                    "Unknown CPU"
                    if runtime_platform.is_macos
                    else sanitize_cpu_display_name(platform.processor()) or "Unknown CPU"
                ),
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
    if runtime_platform.is_linux:
        resolved_cpus: list[JSONDict] = []
        for cpu in cpu_info:
            package_counts = (
                kernel_package_counts(cpu)
                if cpu.get("topology_scope") == "aggregate"
                and cpu.get("architecture") in ("x86_64", "i386", "i486", "i586", "i686")
                else []
            )
            if package_counts:
                for package in package_counts:
                    row = cpu.copy()
                    row.update(
                        {
                            "socket_id": package.package_id,
                            "physical_cores": package.physical_cores,
                            "logical_cores": package.logical_cores,
                            "online_cpu_ids": list(package.online_cpu_ids),
                        }
                    )
                    row["topology_scope"] = "package"
                    row["lscpu_topology_status"] = cpu.get("topology_status")
                    row["topology_status"] = "available"
                    row["package_count"] = len(package_counts)
                    if len(package_counts) > 1:
                        row["name"] = f"CPU package {package.package_id}"
                    row["device_id"] = create_device_id("cpu", package.package_id)
                    row["online_logical_cores"] = package.logical_cores
                    row["physical_count_source"] = "x86_kernel_package_relationships"
                    row["logical_count_source"] = "x86_kernel_package_relationships"
                    resolved_cpus.append(row)
            else:
                resolved_cpus.append(cpu)
        cpu_info = resolved_cpus
        thermal_readings = read_cpu_temperatures()
        for cpu in cpu_info:
            socket_id = cpu.get("socket_id")
            cpu["temperature_celsius"] = (
                thermal_readings.package_temperatures.get(socket_id)
                if isinstance(socket_id, int)
                else None
            )
            if len(cpu_info) == 1 and cpu["temperature_celsius"] is None:
                cpu["temperature_celsius"] = thermal_readings.aggregate_temperature
                if cpu["temperature_celsius"] is None and cpu.get("package_count") == 1:
                    cpu["temperature_celsius"] = thermal_readings.single_package_temperature
    elif runtime_platform.is_macos:
        metadata = read_darwin_cpu_metadata(executor)
        cpu_info[0].update(metadata)
        cpu_info[0]["current_freq_mhz"] = None
    if runtime_platform.is_linux:
        _apply_rapl_power(cpu_info, rapl_energy_cache)
    if cpu_info:
        overall_usage = psutil.cpu_percent(interval=None)
        for cpu in cpu_info:
            cpu["usage_percent"] = overall_usage
            cpu["display_name"] = build_device_display_name(cpu.get("name"))
    return cpu_info
