"""SoAI - Hardware snapshot metrics extraction and normalization [backend/features/api/routes/hardware/hardware_history_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.hardware.snapshot_lookup import (
    find_disk_snapshot_entry,
    find_network_snapshot_selection,
    find_network_speed_entry,
)
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from features.api.routes.hardware.hardware_numeric import safe_numeric

__all__ = (
    "build_history_stream_update",
    "extract_cpu_metrics",
    "extract_disk_metrics",
    "extract_gpu_metrics",
    "extract_network_metrics",
)


def extract_cpu_metrics(snapshot: JSONDict) -> dict[str, float] | None:
    cpu_raw = snapshot.get("cpu")
    cpu_info = cpu_raw if isinstance(cpu_raw, dict) else {}
    metrics: dict[str, float] = {}
    utilization_value = safe_numeric(cpu_info.get("usage_percent"), "cpu.usage_percent")
    if utilization_value is not None:
        metrics["usage_percent"] = utilization_value
    temp_value = safe_numeric(cpu_info.get("temperature_celsius"), "cpu.temperature_celsius")
    if temp_value is not None:
        metrics["temperature_celsius"] = temp_value
    power_value = safe_numeric(cpu_info.get("power_draw_watts"), "cpu.power_draw_watts")
    if power_value is not None:
        metrics["power_draw_watts"] = power_value
    power_limit_value = safe_numeric(cpu_info.get("power_limit_watts"), "cpu.power_limit_watts")
    if power_limit_value is not None:
        metrics["power_limit_watts"] = power_limit_value
    memory_raw = snapshot.get("memory")
    memory_info = memory_raw if isinstance(memory_raw, dict) else {}
    memory_percent = safe_numeric(memory_info.get("percent_used"), "memory.percent_used")
    if memory_percent is not None:
        metrics["memory_percent"] = memory_percent
    return metrics or None


def extract_gpu_metrics(snapshot: JSONDict, gpu_index: int | None) -> dict[str, float] | None:
    if gpu_index is None:
        return None
    gpu_raw = snapshot.get("gpu")
    gpu_section = gpu_raw if isinstance(gpu_raw, dict) else {}
    gpus = gpu_section.get("gpus")
    if not isinstance(gpus, list):
        return None
    entry: JSONDict | None = None
    for gpu in gpus:
        if not isinstance(gpu, dict):
            continue
        if gpu.get("index") == gpu_index:
            entry = gpu
            break
    if entry is None:
        return None
    metrics: dict[str, float] = {}
    util_value = safe_numeric(entry.get("utilization"), f"gpu.{gpu_index}.utilization")
    if util_value is not None:
        metrics["utilization"] = util_value
    mem_value = safe_numeric(entry.get("percent_used"), f"gpu.{gpu_index}.percent_used")
    if mem_value is not None:
        metrics["percent_used"] = mem_value
    temp_value = safe_numeric(entry.get("temperature"), f"gpu.{gpu_index}.temperature")
    if temp_value is not None:
        metrics["temperature"] = temp_value
    power_value = safe_numeric(entry.get("power_draw_watts"), f"gpu.{gpu_index}.power_draw_watts")
    if power_value is not None:
        metrics["power_draw_watts"] = power_value
    power_limit_value = safe_numeric(
        entry.get("power_limit_watts"),
        f"gpu.{gpu_index}.power_limit_watts",
    )
    if power_limit_value is not None:
        metrics["power_limit_watts"] = power_limit_value
    return metrics or None


def extract_disk_metrics(snapshot: JSONDict, identifier: str | None) -> dict[str, float] | None:
    if not identifier:
        return None
    entry = find_disk_snapshot_entry(snapshot, identifier)
    if not entry:
        return None
    metrics: dict[str, float] = {}
    total_value = safe_numeric(entry.get("total_bytes"), "disk.total_bytes")
    if total_value is not None:
        metrics["total_bytes"] = total_value
    used_value = safe_numeric(entry.get("used_bytes"), "disk.used_bytes")
    if used_value is not None:
        metrics["used_bytes"] = used_value
    free_value = safe_numeric(entry.get("free_bytes"), "disk.free_bytes")
    if free_value is not None:
        metrics["free_bytes"] = free_value
    percent_value = safe_numeric(entry.get("percent_used"), "disk.percent_used")
    if percent_value is not None:
        metrics["percent_used"] = percent_value
    return metrics or None


def extract_network_metrics(snapshot: JSONDict, identifier: str | None) -> dict[str, float] | None:
    if not identifier:
        return None
    selection = find_network_snapshot_selection(snapshot, identifier)
    iface_name = selection.interface_name
    stats_dict = selection.stats or {}
    metrics: dict[str, float] = {}
    for source_key, metric_key in (
        ("bytes_sent", "bytes_sent"),
        ("bytes_recv", "bytes_recv"),
        ("packets_sent", "packets_sent"),
        ("packets_recv", "packets_recv"),
        ("errin", "errin"),
        ("errout", "errout"),
        ("dropin", "dropin"),
        ("dropout", "dropout"),
    ):
        value = safe_numeric(stats_dict.get(source_key), f"network.{source_key}")
        if value is not None:
            metrics[metric_key] = value
    speed_entry = find_network_speed_entry(snapshot, iface_name, selection.device_id)
    if speed_entry is not None:
        upload = safe_numeric(speed_entry.get("upload_mbps"), "network.upload_mbps")
        download = safe_numeric(speed_entry.get("download_mbps"), "network.download_mbps")
        if upload is not None:
            metrics["upload_mbps"] = upload
        if download is not None:
            metrics["download_mbps"] = download
    return metrics or None


def build_history_stream_update(
    snapshot: JSONDict,
    component: str,
    gpu_index: int | None,
    identifier: str | None = None,
) -> JSONDict | None:
    timestamp_value = safe_numeric(
        snapshot.get("timestamp_ms"),
        "snapshot.timestamp_ms",
        default=epoch_ms(),
    )
    timestamp_ms = int(timestamp_value if timestamp_value is not None else epoch_ms())
    component_lower = component.lower()
    if component_lower == "cpu":
        metrics = extract_cpu_metrics(snapshot)
    elif component_lower == "gpu":
        metrics = extract_gpu_metrics(snapshot, gpu_index)
    elif component_lower == "disk":
        metrics = extract_disk_metrics(snapshot, identifier)
    elif component_lower == "network":
        metrics = extract_network_metrics(snapshot, identifier)
    else:
        metrics = None
    if not metrics:
        return None
    payload: JSONDict = {
        "timestamp_ms": timestamp_ms,
        "component": component_lower,
        "metrics": metrics,
    }
    if component_lower == "gpu":
        payload["gpu_index"] = gpu_index
    if component_lower in {"disk", "network"} and identifier:
        payload["identifier"] = identifier
    return payload
