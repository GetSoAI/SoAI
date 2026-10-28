"""SoAI - Database hardware metrics logging operations [backend/database/repositories/hardware/logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import sqlite3
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.constants import NETWORK_INTERFACE_STAT_KEYS
from core.hardware.snapshot_lookup import find_network_speed_entry
from core.timing.epoch import epoch_ms
from core.validation.byte_sizes import coerce_optional_size_bytes
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_optional_non_negative_int_strict,
)
from core.validation.text_numbers import coerce_float_from_text, coerce_int_from_text
from database.core.sqlite_values import SQLiteValue

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "resolve_hardware_sample_timestamp_ms",
    "sync_log_hardware_metrics",
)


def _none_if_blank_string(value: JSONValue) -> JSONValue | None:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def resolve_hardware_sample_timestamp_ms(info: JSONDict) -> int:
    timestamp_raw = info.get("timestamp_ms")
    if isinstance(timestamp_raw, int):
        return int(timestamp_raw)
    if isinstance(timestamp_raw, float) and math.isfinite(timestamp_raw):
        return int(timestamp_raw)
    return epoch_ms()


def _observation_timestamp(metadata: JSONValue, aggregate: int) -> int | None:
    if not isinstance(metadata, dict):
        raise ValidationError("Hardware history observation must be an object.")
    status = metadata.get("status")
    checked = metadata.get("checked_at_ms")
    observed = metadata.get("observed_at_ms")
    sampled = metadata.get("sampled_current")
    if status not in ("available", "partial", "stale", "unavailable", "disconnected"):
        raise ValidationError("Hardware history observation status is invalid.")
    require_non_negative_int_strict(
        checked, error_message="Hardware history check timestamp is invalid."
    )
    require_optional_non_negative_int_strict(
        observed, error_message="Hardware history observation timestamp is invalid."
    )
    if "sampled_current" in metadata and not isinstance(sampled, bool):
        raise ValidationError("Hardware history sample authority is invalid.")
    if status in ("available", "partial") and observed is None:
        raise ValidationError("Hardware history observation timestamp is missing.")
    if status not in ("available", "partial") or sampled is False:
        return None
    if sampled is True:
        return observed if isinstance(observed, int) else None
    return aggregate if observed == aggregate else None


def sync_log_hardware_metrics(
    conn: sqlite3.Connection,
    info: JSONDict,
    cleared_through_ms: int | None = None,
) -> None:
    if cleared_through_ms is not None:
        require_non_negative_int_strict(
            cleared_through_ms, error_message="Hardware history reset cutoff is invalid."
        )
    current_time = resolve_hardware_sample_timestamp_ms(info)
    statuses = info.get("component_status")
    if statuses is not None and not isinstance(statuses, dict):
        raise ValidationError("Hardware history component status must be an object.")
    times = {
        component: _observation_timestamp(metadata, current_time)
        for component, metadata in (statuses or {}).items()
    }
    disk_values = info.get("disk")
    disk_times = {
        index: _observation_timestamp(disk["observation_status"], current_time)
        for index, disk in enumerate(disk_values if isinstance(disk_values, list) else [])
        if isinstance(disk, dict) and "observation_status" in disk
    }
    memory_time = times.get("memory", current_time)
    rate_time = times.get("network_speed", current_time)
    for component, timestamp in times.items():
        if (
            cleared_through_ms is not None
            and timestamp is not None
            and timestamp <= cleared_through_ms
        ):
            times[component] = None
    legacy_time: int | None = current_time
    if cleared_through_ms is not None and current_time <= cleared_through_ms:
        legacy_time = None
    cpu_time = times.get("cpus", legacy_time)
    gpu_time = times.get("gpu", legacy_time)
    disk_time = times.get("disk", legacy_time)
    network_time = times.get("network", legacy_time)
    rate_epochs: dict[str, int] = {}
    rate_status = statuses.get("network_speed") if isinstance(statuses, dict) else None
    speed_samples = info.get("network_speed")
    if (
        isinstance(rate_status, dict)
        and rate_status.get("sampled_current") is True
        and isinstance(speed_samples, dict)
    ):
        for name, sample in speed_samples.items():
            timestamp = sample.get("observed_at_ms") if isinstance(sample, dict) else None
            rate_epochs[name] = require_non_negative_int_strict(
                timestamp, error_message="Hardware history network sample timestamp is invalid."
            )
    cpu_info_list, mem_info = (info.get("cpus"), info.get("memory"))
    if cpu_time is not None and cpu_info_list and isinstance(cpu_info_list, list | tuple):
        mem_percent = (
            coerce_float_from_text(mem_info.get("percent_used"), default=None)
            if isinstance(mem_info, dict) and memory_time == cpu_time
            else None
        )
        cpu_rows: list[tuple[SQLiteValue, ...]] = []
        for cpu_entry in cpu_info_list:
            if isinstance(cpu_entry, dict) and (device_id := cpu_entry.get("device_id")):
                cpu_rows.append(
                    (
                        cpu_time,
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
    if gpu_time is not None and gpus and isinstance(gpus, list | tuple):
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
                        gpu_time,
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
        for index, disk in enumerate(disks):
            row_time = disk_times.get(index, disk_time)
            if row_time is None or (
                cleared_through_ms is not None and row_time <= cleared_through_ms
            ):
                continue
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
                        row_time,
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
    interfaces_raw = network_info.get("interfaces")
    interfaces = interfaces_raw if isinstance(interfaces_raw, list | tuple) else []
    interface_map = {
        name: iface.get("device_id")
        for iface in interfaces
        if isinstance(iface, dict)
        and isinstance(name := iface.get("name"), str)
        and name
        and iface.get("device_id")
    }
    if network_stats or (rate_time is not None and info.get("network_speed")):
        network_rows: list[tuple[SQLiteValue, ...]] = []
        for iface in dict.fromkeys([*network_stats, *interface_map]):
            counters = network_stats.get(iface, {})
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
            speed_entry = (
                (find_network_speed_entry(info, str(iface), str(device_id)) or {})
                if rate_time is not None
                else {}
            )
            actual_rate_time = rate_epochs.get(
                str(iface), rate_epochs.get(str(device_id), rate_time)
            )
            if (
                cleared_through_ms is not None
                and actual_rate_time is not None
                and actual_rate_time <= cleared_through_ms
            ):
                actual_rate_time = None
            upload = _none_if_blank_string(speed_entry.get("upload_mbps"))
            download = _none_if_blank_string(speed_entry.get("download_mbps"))
            counter_values = tuple(
                coerce_int_from_text(stats_dict.get(key), default=None)
                for key in NETWORK_INTERFACE_STAT_KEYS
            )
            speed_values = (
                coerce_float_from_text(upload, default=None),
                coerce_float_from_text(download, default=None),
            )
            identity = (str(device_id), str(iface))
            if network_time is not None and iface in network_stats:
                combined_speeds = speed_values if actual_rate_time == network_time else (None, None)
                network_rows.append((network_time, *identity, *counter_values, *combined_speeds))
            if (
                actual_rate_time is not None
                and (actual_rate_time != network_time or iface not in network_stats)
                and speed_entry
            ):
                network_rows.append(
                    (
                        actual_rate_time,
                        *identity,
                        *((None,) * len(NETWORK_INTERFACE_STAT_KEYS)),
                        *speed_values,
                    )
                )
        if network_rows:
            conn.executemany(
                "INSERT OR IGNORE INTO hardware_network_history (observed_at_ms, device_id, interface, bytes_sent, bytes_recv, packets_sent, packets_recv, errin, errout, dropin, dropout, upload_mbps, download_mbps) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(observed_at_ms, device_id, interface) DO UPDATE SET bytes_sent = COALESCE(hardware_network_history.bytes_sent, excluded.bytes_sent), bytes_recv = COALESCE(hardware_network_history.bytes_recv, excluded.bytes_recv), packets_sent = COALESCE(hardware_network_history.packets_sent, excluded.packets_sent), packets_recv = COALESCE(hardware_network_history.packets_recv, excluded.packets_recv), errin = COALESCE(hardware_network_history.errin, excluded.errin), errout = COALESCE(hardware_network_history.errout, excluded.errout), dropin = COALESCE(hardware_network_history.dropin, excluded.dropin), dropout = COALESCE(hardware_network_history.dropout, excluded.dropout), upload_mbps = COALESCE(hardware_network_history.upload_mbps, excluded.upload_mbps), download_mbps = COALESCE(hardware_network_history.download_mbps, excluded.download_mbps)",
                network_rows,
            )
