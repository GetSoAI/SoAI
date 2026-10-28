"""SoAI - Disk partition and I/O information collection [backend/hardware/storage/disk_info.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import psutil

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ProcessError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.mount_filters import is_internal_mount_entry
from core.logging.trace import get_logger
from core.runtime.platform import get_runtime_platform
from core.serialization.json_parsing import parse_json_dict
from core.timing.epoch import epoch_ms
from hardware.operations import create_device_id
from hardware.storage.disk_io_snapshot import (
    collect_disk_io_counters,
    find_disk_io_entry,
    project_disk_io_counters,
)
from hardware.storage.zfs_mounts import apply_zfs_storage_metadata, get_zfs_mount_info

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("DiskInventoryDiagnostic", "DiskInventoryResult", "get_disk_info")

DISK_QUERY_EXCEPTIONS: tuple[type[Exception], ...] = (OSError,) + RECOVERABLE_EXCEPTIONS

ZFS_QUERY_EXCEPTIONS: tuple[type[Exception], ...] = (ProcessError,) + DISK_QUERY_EXCEPTIONS

LOGGER_NAME = "SoAI.hardware.storage.disk_info"
OPERATION_HARDWARE_STORAGE_GET_DISK_INFO = "hardware_storage.get_disk_info"
OPERATION_HARDWARE_STORAGE_GET_DISK_INFO_ZFS_MOUNTS = "hardware_storage.get_disk_info.zfs_mounts"


@dataclass(frozen=True, slots=True)
class DiskInventoryDiagnostic:
    scope: Literal["item", "partitions", "block_metadata", "io", "zfs"]
    reason: str
    item_index: int | None = None


@dataclass(frozen=True, slots=True)
class DiskInventoryResult:
    entries: list[JSONDict]
    status: Literal["complete", "partial", "unavailable"]
    diagnostics: tuple[DiskInventoryDiagnostic, ...] = ()
    failed_item_count: int = 0


@dataclass(frozen=True, slots=True)
class BlockDeviceMetadata:
    entries: dict[str, JSONDict]
    status: Literal["available", "partial", "unavailable", "not_applicable"]
    failures: tuple[str, ...] = ()


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


def _collect_block_device_metadata(executor: CommandExecutorProtocol) -> BlockDeviceMetadata:
    if not get_runtime_platform().is_linux:
        return BlockDeviceMetadata({}, "not_applicable")
    try:
        result = executor.execute(
            [
                "lsblk",
                "--bytes",
                "--json",
                "--output",
                "NAME,PATH,SERIAL,WWN,UUID,PTUUID,KNAME,TYPE",
            ],
            timeout=10,
            shell=False,
            use_sudo=False,
        )
    except DISK_QUERY_EXCEPTIONS:
        return BlockDeviceMetadata({}, "unavailable", ("query_unavailable",))
    if result.return_code != 0:
        return BlockDeviceMetadata({}, "unavailable", ("query_failed",))
    if not result.stdout:
        return BlockDeviceMetadata({}, "unavailable", ("missing_payload",))
    try:
        payload = parse_json_dict(result.stdout, field="lsblk output")
    except ValidationError:
        return BlockDeviceMetadata({}, "unavailable", ("malformed_payload",))
    entries = payload.get("blockdevices")
    if not isinstance(entries, list):
        return BlockDeviceMetadata({}, "unavailable", ("malformed_payload",))
    metadata: dict[str, JSONDict] = {}
    failures: list[str] = []

    def _flatten(items: list[JSONValue]) -> None:
        for entry in items:
            if not isinstance(entry, dict):
                failures.append("malformed_item")
                continue
            path_value = entry.get("path") or entry.get("name")
            if isinstance(path_value, str) and path_value.strip():
                metadata[_normalize_dev_path(path_value)] = {
                    key: entry.get(key) for key in _BLOCK_META_KEYS
                }
            else:
                failures.append("malformed_item")
            children = entry.get("children")
            if isinstance(children, list):
                _flatten(children)
            elif children is not None:
                failures.append("malformed_item")

    _flatten(entries)
    return BlockDeviceMetadata(metadata, "partial" if failures else "available", tuple(failures))


def get_disk_info(executor: CommandExecutorProtocol) -> DiskInventoryResult:
    logger = get_logger(LOGGER_NAME)
    disks: list[JSONDict] = []
    known_mounts: set[str] = set()
    block_result = _collect_block_device_metadata(executor)
    diagnostics = [
        DiskInventoryDiagnostic("block_metadata", reason) for reason in block_result.failures
    ]
    io_result = collect_disk_io_counters()
    if not io_result.available:
        diagnostics.append(DiskInventoryDiagnostic("io", "query_unavailable"))
    partitions_available = True
    try:
        partitions = psutil.disk_partitions(all=True)
    except DISK_QUERY_EXCEPTIONS as exception:
        partitions = []
        partitions_available = False
        reason = (
            "permission_denied" if isinstance(exception, PermissionError) else "query_unavailable"
        )
        diagnostics.append(DiskInventoryDiagnostic("partitions", reason))
    for item_index, partition in enumerate(partitions):
        try:
            mountpoint = partition.mountpoint
        except AttributeError:
            mountpoint = ""
        try:
            fstype_value = partition.fstype
        except AttributeError:
            fstype_value = None
        if str(fstype_value or "").strip().lower() == "cgroup2" or is_internal_mount_entry(
            mountpoint, fstype_value
        ):
            continue
        try:
            device = partition.device
        except AttributeError:
            device = None
        device_meta = block_result.entries.get(device) if device else None
        primary_device_id = _get_first_truthy(
            device_meta,
            "uuid",
            "ptuuid",
            "wwn",
            "serial",
            default=device,
        )
        try:
            device_id = create_device_id("disk", primary_device_id)
        except ValidationError:
            diagnostics.append(DiskInventoryDiagnostic("item", "malformed_identity", item_index))
            continue
        try:
            usage = psutil.disk_usage(mountpoint)
        except OSError as exception:
            reason = (
                "permission_denied"
                if isinstance(exception, PermissionError)
                else (
                    "disappeared"
                    if isinstance(exception, FileNotFoundError)
                    else "usage_unavailable"
                )
            )
            diagnostics.append(DiskInventoryDiagnostic("item", reason, item_index))
            failed_entry: JSONDict = {
                "device_id": device_id,
                "filesystem": device,
                "mount": mountpoint,
                "fstype": fstype_value,
                "observation_status": {
                    "status": "unavailable",
                    "observed_at_ms": None,
                    "checked_at_ms": epoch_ms(),
                },
            }
            if device_meta:
                failed_entry.update({key: value for key, value in device_meta.items() if value})
            disks.append(failed_entry)
            known_mounts.add(mountpoint)
            continue
        try:
            opts_value = partition.opts
        except AttributeError:
            opts_value = None
        entry: JSONDict = {
            "device_id": device_id,
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
        io_entry = find_disk_io_entry(device, device_meta, io_result.counters)
        if io_entry is not None:
            io_snapshot = project_disk_io_counters(io_entry)
            if io_snapshot.values:
                entry["io"] = io_snapshot.values
            if io_snapshot.malformed:
                diagnostics.append(DiskInventoryDiagnostic("item", "malformed_io", item_index))
        disks.append(entry)
        known_mounts.add(mountpoint)
    try:
        disks.extend(get_zfs_mount_info(executor, known_mounts))
    except ZFS_QUERY_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to query ZFS mount information (non-critical).",
            operation=OPERATION_HARDWARE_STORAGE_GET_DISK_INFO_ZFS_MOUNTS,
            level="debug",
        )
        diagnostics.append(DiskInventoryDiagnostic("zfs", "query_unavailable"))
    status: Literal["complete", "partial", "unavailable"] = "complete"
    if not partitions_available and not disks:
        status = "unavailable"
    elif diagnostics:
        status = "partial"
    failed_items = {item.item_index for item in diagnostics if item.item_index is not None}
    return DiskInventoryResult(disks, status, tuple(diagnostics), len(failed_items))
