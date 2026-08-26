"""SoAI - Disk partition and I/O information collection [backend/hardware/storage/disk_info.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING

import psutil

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ProcessError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.mount_filters import is_internal_mount_entry
from core.logging.trace import get_logger
from core.platform.protocols import PsutilDiskIOCountersProtocol
from core.runtime.platform import get_runtime_platform
from core.serialization.json_parsing import parse_json_dict
from hardware.operations import create_device_id
from hardware.storage.zfs_mounts import apply_zfs_storage_metadata, get_zfs_mount_info

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("get_disk_info",)

LOGGER_NAME = "SoAI.hardware.storage.disk_info"
OPERATION_HARDWARE_STORAGE_GET_DISK_INFO = "hardware_storage.get_disk_info"
OPERATION_HARDWARE_STORAGE_GET_DISK_INFO_DISK_IO_COUNTERS = (
    "hardware_storage.get_disk_info.disk_io_counters"
)
OPERATION_HARDWARE_STORAGE_GET_DISK_INFO_DISK_USAGE = "hardware_storage.get_disk_info.disk_usage"
OPERATION_HARDWARE_STORAGE_GET_DISK_INFO_ZFS_MOUNTS = "hardware_storage.get_disk_info.zfs_mounts"


_BLOCK_META_KEYS: tuple[str, ...] = ("serial", "wwn", "uuid", "ptuuid", "kname", "type")


def _get_first_truthy(
    source: JSONDict | None,
    *keys: str,
    default: str | float | None = None,
) -> str | int | float | None:
    if not source:
        return default
    for key in keys:
        value = source.get(key)
        if isinstance(value, str | int | float) and value:
            return value
    return default


def _normalize_dev_path(path: str) -> str:
    return path if path.startswith("/dev/") else f"/dev/{path}"


def _find_io_entry(
    device: str | None,
    device_meta: JSONDict | None,
    io_stats: Mapping[str, PsutilDiskIOCountersProtocol],
) -> PsutilDiskIOCountersProtocol | None:
    logger = get_logger(LOGGER_NAME)
    candidates: list[str] = []
    if isinstance(device, str) and device:
        candidates.append(device)
        try:
            if basename := os.path.basename(device):
                candidates.append(basename)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to normalize partition device basename (non-critical).",
                operation=OPERATION_HARDWARE_STORAGE_GET_DISK_INFO,
                details={"device": device},
                level="debug",
            )
    if isinstance(device_meta, dict):
        for key in ("kname", "path", "name"):
            if isinstance((value := device_meta.get(key)), str) and value.strip():
                candidates.append(value.strip())
    for candidate in candidates:
        if io_entry := io_stats.get(candidate) or io_stats.get(_normalize_dev_path(candidate)):
            return io_entry
    return None


def _collect_block_device_metadata(
    executor: CommandExecutorProtocol,
) -> dict[str, JSONDict]:
    runtime_platform = get_runtime_platform()
    if not runtime_platform.is_linux:
        return {}
    result = executor.execute(
        ["lsblk", "--bytes", "--json", "-O"],
        timeout=10,
        shell=False,
        use_sudo=False,
    )
    if result.return_code != 0 or not result.stdout:
        return {}
    try:
        payload = parse_json_dict(result.stdout, field="lsblk output")
    except ValidationError:
        return {}
    metadata: dict[str, JSONDict] = {}

    def _flatten(entries: JSONValue) -> None:
        if not isinstance(entries, list):
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            path_value = entry.get("path") or entry.get("name")
            if isinstance(path_value, str) and path_value:
                metadata[_normalize_dev_path(path_value)] = {
                    key: entry.get(key) for key in _BLOCK_META_KEYS
                }
            children = entry.get("children")
            if isinstance(children, list):
                _flatten(children)

    _flatten(payload.get("blockdevices"))
    return metadata


def get_disk_info(executor: CommandExecutorProtocol) -> list[JSONDict]:
    logger = get_logger(LOGGER_NAME)
    disks: list[JSONDict] = []
    known_mounts: set[str] = set()
    block_metadata = _collect_block_device_metadata(executor)
    io_stats: Mapping[str, PsutilDiskIOCountersProtocol] = {}
    try:
        io_stats = psutil.disk_io_counters(perdisk=True)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to query disk I/O counters (non-critical).",
            operation=OPERATION_HARDWARE_STORAGE_GET_DISK_INFO_DISK_IO_COUNTERS,
            level="trace",
        )
        io_stats = {}
    for partition in psutil.disk_partitions(all=True):
        try:
            mountpoint = partition.mountpoint
        except AttributeError:
            mountpoint = ""
        try:
            fstype_value = partition.fstype
        except AttributeError:
            fstype_value = None
        if is_internal_mount_entry(mountpoint, fstype_value):
            continue
        try:
            usage = psutil.disk_usage(mountpoint)
        except OSError as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to query disk usage for mount point (non-critical).",
                operation=OPERATION_HARDWARE_STORAGE_GET_DISK_INFO_DISK_USAGE,
                details={"mountpoint": mountpoint, "fstype": fstype_value},
                level="debug",
            )
            continue
        try:
            device = partition.device
        except AttributeError:
            device = None
        device_meta = block_metadata.get(device) if device else None
        primary_device_id = _get_first_truthy(
            device_meta,
            "uuid",
            "ptuuid",
            "wwn",
            "serial",
            default=device,
        )
        if primary_device_id is None:
            continue
        try:
            opts_value = partition.opts
        except AttributeError:
            opts_value = None
        entry: JSONDict = {
            "device_id": create_device_id("disk", primary_device_id),
            "filesystem": device,
            "mount": mountpoint,
            "fstype": fstype_value,
            "opts": opts_value,
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "total_gb": round(usage.total / 1024**3, 2),
            "used_gb": round(usage.used / 1024**3, 2),
            "free_gb": round(usage.free / 1024**3, 2),
            "percent_used": usage.percent,
        }
        if device_meta:
            entry.update({key: value for key, value in device_meta.items() if value})
        apply_zfs_storage_metadata(entry, fstype_value)
        io_entry = _find_io_entry(device, device_meta, io_stats)
        if io_entry is not None:
            io_dict: JSONDict = {}
            try:
                read_bytes_value = io_entry.read_bytes
            except AttributeError:
                read_bytes_value = None
            if isinstance(read_bytes_value, int | float):
                io_dict["read_bytes"] = int(read_bytes_value)
            try:
                write_bytes_value = io_entry.write_bytes
            except AttributeError:
                write_bytes_value = None
            if isinstance(write_bytes_value, int | float):
                io_dict["write_bytes"] = int(write_bytes_value)
            try:
                read_count_value = io_entry.read_count
            except AttributeError:
                read_count_value = None
            if isinstance(read_count_value, int | float):
                io_dict["read_count"] = int(read_count_value)
            try:
                write_count_value = io_entry.write_count
            except AttributeError:
                write_count_value = None
            if isinstance(write_count_value, int | float):
                io_dict["write_count"] = int(write_count_value)
            try:
                read_time_value = io_entry.read_time
            except AttributeError:
                read_time_value = None
            if isinstance(read_time_value, int | float):
                io_dict["read_time_ms"] = int(read_time_value)
            try:
                write_time_value = io_entry.write_time
            except AttributeError:
                write_time_value = None
            if isinstance(write_time_value, int | float):
                io_dict["write_time_ms"] = int(write_time_value)
            try:
                busy_time_value = io_entry.busy_time
            except AttributeError:
                busy_time_value = None
            if isinstance(busy_time_value, int | float):
                io_dict["busy_time_ms"] = int(busy_time_value)
            if io_dict:
                entry["io"] = io_dict
        disks.append(entry)
        known_mounts.add(mountpoint)
    try:
        disks.extend(get_zfs_mount_info(executor, known_mounts))
    except ProcessError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to query ZFS mount information (non-critical).",
            operation=OPERATION_HARDWARE_STORAGE_GET_DISK_INFO_ZFS_MOUNTS,
            level="debug",
        )
    return disks
