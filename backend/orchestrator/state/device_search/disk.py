"""SoAI - Disk/volume device search candidates [backend/orchestrator/state/device_search/disk.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from orchestrator.state.device_search.collector import (
    CandidateCollector,
    device_terms,
    resolve_device_identifier,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("collect_disk_candidates",)

_DISK_METADATA_KEYS: tuple[str, ...] = (
    "mount",
    "filesystem",
    "fstype",
    "size",
    "used",
    "available",
    "used_percent",
    "percent_used",
    "total_bytes",
    "used_bytes",
    "free_bytes",
)


def collect_disk_candidates(hardware_snapshot: JSONDict, collector: CandidateCollector) -> None:
    disk_list = hardware_snapshot.get("disk") or []
    for disk in disk_list if isinstance(disk_list, list) else []:
        if not isinstance(disk, dict):
            continue
        mount = disk.get("mount") or disk.get("filesystem")
        device_id = resolve_device_identifier(disk.get("device_id"), disk.get("filesystem"), mount)
        if device_id is None:
            continue
        disk_name_val = disk.get("name")
        disk_fs_val = disk.get("filesystem")
        base_name = str(disk_name_val or mount or disk_fs_val or "").strip()
        pretty_name = base_name or "Volume"
        terms = device_terms(
            "volume",
            "disk",
            "storage",
            disk.get("filesystem"),
            disk.get("fstype"),
            disk.get("size"),
            disk.get("used"),
            disk.get("available"),
        )
        metadata = {key: disk.get(key) for key in _DISK_METADATA_KEYS}
        metadata["device_id"] = device_id
        collector.add_candidate(
            device_type="VOLUME",
            identifier=device_id,
            name=pretty_name,
            search_terms=terms,
            metadata=metadata,
        )
