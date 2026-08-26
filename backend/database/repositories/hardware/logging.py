"""SoAI - Database hardware metrics logging operations [backend/database/repositories/hardware/logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import sqlite3
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.hardware.constants import NETWORK_INTERFACE_STAT_KEYS
from core.hardware.snapshot_lookup import find_network_speed_entry
from core.timing.epoch import epoch_ms
from core.validation.byte_sizes import coerce_optional_size_bytes
from core.validation.text_numbers import coerce_float_from_text, coerce_int_from_text
from database.core.sqlite_values import SQLiteValue

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("sync_log_hardware_metrics",)


def _none_if_blank_string(value: JSONValue) -> JSONValue | None:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def sync_log_hardware_metrics(
    conn: sqlite3.Connection,
    info: JSONDict,
) -> None:
    timestamp_raw = info.get("timestamp_ms")
    if isinstance(timestamp_raw, int):
        current_time = int(timestamp_raw)
    elif isinstance(timestamp_raw, float):
        current_time = int(timestamp_raw) if math.isfinite(timestamp_raw) else epoch_ms()
    else:
        current_time = epoch_ms()
    cpu_info_list, mem_info = (info.get("cpus"), info.get("memory"))
    if cpu_info_list and isinstance(cpu_info_list, list | tuple):
        mem_percent = (
            coerce_float_from_text(mem_info.get("percent_used"), default=None)
            if isinstance(mem_info, dict)
            else None
        )
        cpu_rows: list[tuple[SQLiteValue, ...]] = []
        for cpu_entry in cpu_info_list:
            if isinstance(cpu_entry, dict) and (device_id := cpu_entry.get("device_id")):
                cpu_rows.append(
                    (
                        current_time,
                        str(device_id),
                        coerce_float_from_text(cpu_entry.get("usage_percent"), default=None),
                        coerce_float_from_text(cpu_entry.get("temperature_celsius"), default=None),
                        coerce_float_from_text(cpu_entry.get("power_draw_watts"), default=None),
                        mem_percent,
                        coerce_float_from_text(cpu_entry.get("power_limit_watts"), default=None),
                    ),
                )
        if cpu_rows:
            conn.executemany(
                "INSERT OR IGNORE INTO hardware_cpu_history (observed_at_ms, device_id, usage_percent, temperature_celsius, power_draw_watts, memory_percent, power_limit_watts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                cpu_rows,
            )
    gpu_info = info.get("gpu")
    gpus = gpu_info.get("gpus") if isinstance(gpu_info, dict) else None
    if gpus and isinstance(gpus, list | tuple):
        gpu_rows: list[tuple[SQLiteValue, ...]] = []
        for gpu in gpus:
            if isinstance(gpu, dict) and (device_id := gpu.get("device_id")):
                if gpu.get("telemetry_available") is False:
                    continue
                raw_clock = gpu.get("clock")
                clock_info: Mapping[str, JSONValue] = (
                    raw_clock if isinstance(raw_clock, Mapping) else {}
                )
                clock_core = clock_info.get("core_mhz")
                clock_memory = clock_info.get("memory_mhz")
                clock_core_value = (
                    coerce_float_from_text(clock_core, default=None)
                    if isinstance(clock_core, int | float | str | bool)
                    else None
                )
                clock_memory_value = (
                    coerce_float_from_text(clock_memory, default=None)
                    if isinstance(clock_memory, int | float | str | bool)
                    else None
                )
                gpu_rows.append(
                    (
                        current_time,
                        str(device_id),
                        coerce_int_from_text(gpu.get("index"), default=None),
                        coerce_float_from_text(gpu.get("utilization"), default=None),
                        coerce_float_from_text(gpu.get("percent_used"), default=None),
                        coerce_float_from_text(gpu.get("temperature"), default=None),
                        coerce_float_from_text(gpu.get("power_draw_watts"), default=None),
                        coerce_float_from_text(gpu.get("power_limit_watts"), default=None),
                        clock_core_value,
                        clock_memory_value,
                    ),
                )
        if gpu_rows:
            conn.executemany(
                "INSERT OR IGNORE INTO hardware_gpu_history (observed_at_ms, device_id, gpu_index, utilization, percent_used, temperature, power_draw_watts, power_limit_watts, core_clock_mhz, mem_clock_mhz) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                gpu_rows,
            )
    disks = info.get("disk")
    if disks and isinstance(disks, list | tuple):
        disk_rows: list[tuple[SQLiteValue, ...]] = []
        for disk in disks:
            if (
                isinstance(disk, dict)
                and (device_id := disk.get("device_id"))
                and (mount := (disk.get("mount") or disk.get("filesystem")))
            ):
                total_bytes_value = _none_if_blank_string(disk.get("total_bytes"))
                used_bytes_value = _none_if_blank_string(disk.get("used_bytes"))
                free_bytes_value = _none_if_blank_string(disk.get("free_bytes"))
                available_bytes_value = _none_if_blank_string(disk.get("available"))
                free_value = _none_if_blank_string(disk.get("free"))
                total = (
                    total_bytes_value
                    if total_bytes_value is not None
                    else coerce_optional_size_bytes(disk.get("size"))
                )
                used = (
                    used_bytes_value
                    if used_bytes_value is not None
                    else coerce_optional_size_bytes(disk.get("used"))
                )
                free_fallback_value = (
                    available_bytes_value if available_bytes_value is not None else free_value
                )
                free = (
                    free_bytes_value
                    if free_bytes_value is not None
                    else coerce_optional_size_bytes(free_fallback_value)
                )
                percent_used_value = _none_if_blank_string(disk.get("percent_used"))
                used_percent_value = _none_if_blank_string(disk.get("used_percent"))
                percent = (
                    percent_used_value
                    if percent_used_value is not None
                    else coerce_float_from_text(used_percent_value, default=None)
                )
                device = disk.get("filesystem") or disk.get("device")
                disk_rows.append(
                    (
                        current_time,
                        str(device_id),
                        str(mount),
                        str(device) if device else None,
                        coerce_int_from_text(total, default=None),
                        coerce_int_from_text(used, default=None),
                        coerce_int_from_text(free, default=None),
                        coerce_float_from_text(percent, default=None),
                    ),
                )
        if disk_rows:
            conn.executemany(
                "INSERT OR IGNORE INTO hardware_disk_history (observed_at_ms, device_id, mount, device, total_bytes, used_bytes, free_bytes, percent_used) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                disk_rows,
            )
    network_info_raw = info.get("network")
    network_info = network_info_raw if isinstance(network_info_raw, dict) else {}
    network_stats_raw = network_info.get("stats") if network_info else None
    network_stats = network_stats_raw if isinstance(network_stats_raw, dict) else {}
    if network_stats:
        interfaces_raw = network_info.get("interfaces")
        interfaces = interfaces_raw if isinstance(interfaces_raw, list | tuple) else []
        interface_map = {
            iface.get("name"): iface.get("device_id")
            for iface in interfaces
            if isinstance(iface, dict) and iface.get("name") and iface.get("device_id")
        }
        network_rows: list[tuple[SQLiteValue, ...]] = []
        for iface, counters in network_stats.items():
            if not iface or not (device_id := interface_map.get(iface)):
                continue
            if isinstance(counters, Mapping):
                stats_dict = counters
            elif isinstance(counters, Sequence) and not isinstance(counters, str):
                stats_dict = {
                    stat_key: counters[index]
                    for index, stat_key in enumerate(NETWORK_INTERFACE_STAT_KEYS)
                    if index < len(counters)
                }
            else:
                continue
            speed_entry = find_network_speed_entry(info, str(iface), str(device_id)) or {}
            upload = _none_if_blank_string(speed_entry.get("upload_mbps"))
            download = _none_if_blank_string(speed_entry.get("download_mbps"))
            network_rows.append(
                (
                    current_time,
                    str(device_id),
                    str(iface),
                    coerce_int_from_text(stats_dict.get("bytes_sent"), default=None),
                    coerce_int_from_text(stats_dict.get("bytes_recv"), default=None),
                    coerce_int_from_text(stats_dict.get("packets_sent"), default=None),
                    coerce_int_from_text(stats_dict.get("packets_recv"), default=None),
                    coerce_int_from_text(stats_dict.get("errin"), default=None),
                    coerce_int_from_text(stats_dict.get("errout"), default=None),
                    coerce_int_from_text(stats_dict.get("dropin"), default=None),
                    coerce_int_from_text(stats_dict.get("dropout"), default=None),
                    coerce_float_from_text(upload, default=None),
                    coerce_float_from_text(download, default=None),
                ),
            )
        if network_rows:
            conn.executemany(
                "INSERT OR IGNORE INTO hardware_network_history (observed_at_ms, device_id, interface, bytes_sent, bytes_recv, packets_sent, packets_recv, errin, errout, dropin, dropout, upload_mbps, download_mbps) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                network_rows,
            )
