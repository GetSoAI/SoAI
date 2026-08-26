"""SoAI - ZFS mount information collection [backend/hardware/storage/zfs_mounts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.files.findmnt import parse_findmnt_filesystems
from core.files.mount_filters import is_internal_mount_point
from core.os.storage_types import ZFS_STORAGE_READ_ONLY_REASON
from core.system.command_failures import require_command_success
from core.validation.integers import coerce_non_negative_exact_int_or_zero
from hardware.operations import create_device_id

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("apply_zfs_storage_metadata", "get_zfs_mount_info")


def apply_zfs_storage_metadata(entry: JSONDict, filesystem_type: str | None) -> None:
    if not _is_zfs_filesystem_type(filesystem_type):
        return
    entry["storage_backend"] = "zfs"
    entry["read_only"] = True
    entry["read_only_reason"] = ZFS_STORAGE_READ_ONLY_REASON


def get_zfs_mount_info(
    executor: CommandExecutorProtocol,
    known_mounts: set[str],
) -> list[JSONDict]:
    argv = [
        "findmnt",
        "--json",
        "--bytes",
        "--output",
        "SOURCE,TARGET,FSTYPE,SIZE,USED,AVAIL,OPTIONS",
    ]
    result = executor.execute(
        argv,
        timeout=10,
        shell=False,
        use_sudo=False,
    )
    require_command_success(result, argv, operation="hardware.storage.findmnt.zfs")
    disks: list[JSONDict] = []
    for entry in parse_findmnt_filesystems(result.stdout or ""):
        parsed = _parse_zfs_mount(entry, known_mounts)
        if parsed is not None:
            disks.append(parsed)
    return disks


def _parse_zfs_mount(entry: dict[str, JSONValue], known_mounts: set[str]) -> JSONDict | None:
    if not _is_zfs_filesystem_type(str(entry.get("fstype") or "")):
        return None
    source = str(entry.get("source") or "").strip()
    mount_point = str(entry.get("target") or "").strip()
    if not source or not mount_point or mount_point in known_mounts:
        return None
    if is_internal_mount_point(mount_point):
        return None
    total_bytes = coerce_non_negative_exact_int_or_zero(entry.get("size"))
    used_bytes = coerce_non_negative_exact_int_or_zero(entry.get("used"))
    free_bytes = coerce_non_negative_exact_int_or_zero(entry.get("avail"))
    if total_bytes <= 0:
        total_bytes = used_bytes + free_bytes
    percent_used = _calculate_percent_used(total_bytes, used_bytes)
    parsed: JSONDict = {
        "device_id": create_device_id("disk", f"zfs:{source}:{mount_point}"),
        "filesystem": source,
        "mount": mount_point,
        "fstype": "zfs",
        "opts": str(entry.get("options") or "").strip() or None,
        "total_bytes": total_bytes,
        "used_bytes": used_bytes,
        "free_bytes": free_bytes,
        "total_gb": round(total_bytes / 1024**3, 2),
        "used_gb": round(used_bytes / 1024**3, 2),
        "free_gb": round(free_bytes / 1024**3, 2),
        "percent_used": percent_used,
    }
    apply_zfs_storage_metadata(parsed, "zfs")
    return parsed


def _is_zfs_filesystem_type(value: str | None) -> bool:
    return str(value or "").strip().lower() == "zfs"


def _calculate_percent_used(total_bytes: int, used_bytes: int) -> float:
    if total_bytes <= 0 or used_bytes <= 0:
        return 0.0
    return min(round((used_bytes / total_bytes) * 100, 1), 100.0)
