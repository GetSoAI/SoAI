"""SoAI - Hardware system info cache helpers [backend/hardware/manager/system_info_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.hardware.system_info_keys import (
    SYSTEM_INFO_COMPONENT_KEYS_EXCLUDING_CPU,
    SYSTEM_INFO_ORDERED_KEYS_WITH_META,
)
from hardware.operations import sum_vram_gb

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_cached_response",
    "build_final_ordered_info",
    "build_summary",
    "resolve_needed_keys",
)

SYSTEM_INFO_COMPONENT_ORDER: tuple[str, ...] = SYSTEM_INFO_COMPONENT_KEYS_EXCLUDING_CPU
ORDERED_SYSTEM_INFO_KEYS: tuple[str, ...] = SYSTEM_INFO_ORDERED_KEYS_WITH_META
COMPONENT_META_KEYS: tuple[str, ...] = ("summary", "capabilities", "timestamp_ms")
ALL_COMPONENT_KEYS: tuple[str, ...] = SYSTEM_INFO_COMPONENT_KEYS_EXCLUDING_CPU


def resolve_needed_keys(components: Sequence[str] | None) -> set[str]:
    needed_keys = set(components or ALL_COMPONENT_KEYS)
    if "cpu" in needed_keys:
        needed_keys.add("cpus")
    needed_keys.update(COMPONENT_META_KEYS)
    return needed_keys


def build_cached_response(
    *,
    last_full_info: Mapping[str, JSONValue],
    components: Sequence[str],
) -> JSONDict:
    keys_to_return = set(components)
    if "cpu" in keys_to_return:
        keys_to_return.add("cpus")
    keys_to_return.update(COMPONENT_META_KEYS)
    cached_response = {
        component_key: last_full_info[component_key]
        for component_key in keys_to_return
        if component_key in last_full_info
    }
    if "cpu" in components:
        cpu_entries = last_full_info.get("cpus")
        if isinstance(cpu_entries, list) and cpu_entries:
            first_cpu = cpu_entries[0]
            cached_response["cpu"] = first_cpu if isinstance(first_cpu, dict) else {}
        else:
            cached_response["cpu"] = {}
    return cached_response


def build_summary(*, base_snapshot: Mapping[str, JSONValue]) -> JSONDict:
    gpu_snapshot_raw = base_snapshot.get("gpu")
    gpu_snapshot = gpu_snapshot_raw if isinstance(gpu_snapshot_raw, dict) else None
    memory_info = base_snapshot.get("memory")
    summary: JSONDict = {}
    if isinstance(memory_info, dict):
        summary["total_system_ram_gb"] = memory_info.get("total_gb", 0)
    summary["total_vram_gb"] = sum_vram_gb(gpu_snapshot or {})
    ram_value = summary.get("total_system_ram_gb", 0)
    vram_value = summary.get("total_vram_gb", 0)
    ram = float(ram_value) if isinstance(ram_value, int | float) else 0.0
    vram = float(vram_value) if isinstance(vram_value, int | float) else 0.0
    summary["total_system_memory_gb"] = round(ram + vram, 2)
    return summary


def build_final_ordered_info(
    *,
    base_snapshot: Mapping[str, JSONValue],
    summary: Mapping[str, JSONValue],
    capabilities_payload: Mapping[str, JSONValue],
) -> JSONDict:
    final_ordered_info: JSONDict = {"timestamp_ms": base_snapshot.get("timestamp_ms")}
    summary_dict = dict(summary)
    capabilities_dict = dict(capabilities_payload)
    for key in ORDERED_SYSTEM_INFO_KEYS:
        if key == "summary":
            final_ordered_info["summary"] = summary_dict
            continue
        if key == "capabilities":
            final_ordered_info["capabilities"] = capabilities_dict
            continue
        if key in base_snapshot:
            final_ordered_info[key] = base_snapshot[key]
    return final_ordered_info
