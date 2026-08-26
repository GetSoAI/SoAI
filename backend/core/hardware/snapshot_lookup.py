"""SoAI - Hardware snapshot component lookup [backend/core/hardware/snapshot_lookup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.constants import NETWORK_INTERFACE_STAT_KEYS

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "NetworkSnapshotSelection",
    "find_disk_snapshot_entry",
    "find_network_snapshot_selection",
    "find_network_speed_entry",
    "resolve_component_device_id",
)


@dataclass(frozen=True, slots=True)
class NetworkSnapshotSelection:
    interface_name: str | None
    stats: JSONDict | None
    device_id: str | None


def _normalized_path(value: str) -> str:
    return os.path.normcase(os.path.normpath(value.strip())) if value.strip() else ""


def find_disk_snapshot_entry(snapshot: JSONDict, identifier: str) -> JSONDict | None:
    normalized = identifier.strip()
    normalized_lower = normalized.lower()
    normalized_path = _normalized_path(normalized)
    raw_items = snapshot.get("disk")
    disk_items: list[JSONValue] = raw_items if isinstance(raw_items, list) else []
    for item in disk_items:
        if not isinstance(item, dict):
            continue
        device_id = item.get("device_id")
        if isinstance(device_id, str) and device_id.strip().lower() == normalized_lower:
            return dict(item)
        if _path_field_matches(item.get("filesystem"), normalized_path):
            return dict(item)
        if _path_field_matches(item.get("mount"), normalized_path):
            return dict(item)
    return None


def find_network_snapshot_selection(
    snapshot: JSONDict,
    identifier: str,
) -> NetworkSnapshotSelection:
    network_raw = snapshot.get("network")
    network = network_raw if isinstance(network_raw, dict) else {}
    normalized_lower = identifier.strip().lower()
    by_device_selection = _find_network_by_device_id(network, normalized_lower)
    iface_name = by_device_selection.interface_name
    stats_dict = by_device_selection.stats
    device_id = by_device_selection.device_id
    if stats_dict is not None:
        return NetworkSnapshotSelection(iface_name, stats_dict, device_id)
    interface_name, interface_device_id = _find_network_interface(network, normalized_lower)
    if iface_name is None:
        iface_name = interface_name
    if device_id is None:
        device_id = interface_device_id
    network_stats = network.get("stats")
    if isinstance(iface_name, str) and isinstance(network_stats, dict):
        raw = network_stats.get(iface_name)
        if isinstance(raw, dict):
            stats_dict = dict(raw)
        elif isinstance(raw, list | tuple):
            stats_dict = _network_stats_tuple_to_dict(raw)
    return NetworkSnapshotSelection(iface_name, stats_dict, device_id)


def find_network_speed_entry(
    snapshot: JSONDict,
    interface_name: str | None,
    device_id: str | None,
) -> JSONDict | None:
    speed_info_raw = snapshot.get("network_speed")
    if not isinstance(speed_info_raw, dict):
        return None
    normalized_names = {
        value.strip().lower()
        for value in (interface_name, device_id)
        if isinstance(value, str) and value.strip()
    }
    for raw_key, raw_entry in speed_info_raw.items():
        if not isinstance(raw_key, str) or not isinstance(raw_entry, dict):
            continue
        if raw_key.strip().lower() in normalized_names:
            return dict(raw_entry)
    return None


def resolve_component_device_id(component: str, identifier: str, snapshot: JSONDict) -> str:
    ident = identifier.strip()
    ident_lower = ident.lower()
    if component == "cpu":
        return _resolve_cpu_device_id(ident, ident_lower, snapshot)
    if component == "disk":
        entry = find_disk_snapshot_entry(snapshot, identifier)
        if entry is not None:
            device_id = entry.get("device_id")
            if isinstance(device_id, str) and device_id.strip():
                return device_id.strip().lower()
        raise ValidationError(f"Unknown disk identifier '{identifier}'.")
    if component == "network":
        selection = find_network_snapshot_selection(snapshot, identifier)
        if selection.device_id:
            return selection.device_id
        raise ValidationError(f"Unknown network identifier '{identifier}'.")
    raise ValidationError(f"Unknown component '{component}'.")


def _path_field_matches(value: JSONValue, normalized_path: str) -> bool:
    return (
        bool(normalized_path)
        and isinstance(value, str)
        and bool(value.strip())
        and os.path.normcase(os.path.normpath(value.strip())) == normalized_path
    )


def _find_network_interface(
    network: JSONDict,
    normalized_lower: str,
) -> tuple[str | None, str | None]:
    raw_items = network.get("interfaces")
    net_items: list[JSONValue] = raw_items if isinstance(raw_items, list) else []
    for item in net_items:
        if not isinstance(item, dict):
            continue
        device_id = item.get("device_id")
        name = item.get("name")
        if isinstance(device_id, str) and device_id.strip().lower() == normalized_lower:
            return (name if isinstance(name, str) else None, device_id.strip().lower())
        if isinstance(name, str) and name.strip().lower() == normalized_lower:
            return (name, device_id.strip().lower() if isinstance(device_id, str) else None)
    return (None, None)


def _find_network_by_device_id(
    network: JSONDict,
    normalized_lower: str,
) -> NetworkSnapshotSelection:
    by_device_id = network.get("by_device_id")
    if not isinstance(by_device_id, dict):
        return NetworkSnapshotSelection(None, None, None)
    for raw_device_id, raw_entry in by_device_id.items():
        if not isinstance(raw_device_id, str):
            continue
        device_id = raw_device_id.strip().lower()
        if device_id != normalized_lower or not isinstance(raw_entry, dict):
            continue
        raw_name = raw_entry.get("name")
        iface_name = raw_name if isinstance(raw_name, str) else None
        raw_stats = raw_entry.get("stats")
        stats_dict = dict(raw_stats) if isinstance(raw_stats, dict) else None
        return NetworkSnapshotSelection(iface_name, stats_dict, device_id)
    return NetworkSnapshotSelection(None, None, None)


def _network_stats_tuple_to_dict(raw: list[JSONValue] | tuple[JSONValue, ...]) -> JSONDict:
    return {
        stat_key: raw[index]
        for index, stat_key in enumerate(NETWORK_INTERFACE_STAT_KEYS)
        if index < len(raw)
    }


def _resolve_cpu_device_id(ident: str, ident_lower: str, snapshot: JSONDict) -> str:
    raw_items = snapshot.get("cpus")
    cpu_items: list[JSONValue] = raw_items if isinstance(raw_items, list) else []
    for item in cpu_items:
        if not isinstance(item, dict):
            continue
        device_id = item.get("device_id")
        if isinstance(device_id, str) and device_id.strip().lower() == ident_lower:
            return device_id.strip().lower()
        socket_id = item.get("socket_id")
        if socket_id is not None and str(socket_id) == ident:
            if isinstance(device_id, str) and device_id.strip():
                return device_id.strip().lower()
    raise ValidationError(f"Unknown CPU identifier '{ident}'.")
