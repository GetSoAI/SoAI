"""SoAI - Core OS storage types [backend/core/os/storage_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from core.timing.epoch import epoch_ms

__all__ = (
    "ZFS_STORAGE_READ_ONLY_REASON",
    "BlockDevice",
    "FstabEntry",
    "FstabEntryConfig",
    "Partition",
    "PartitionConfig",
    "StorageStatusSnapshot",
    "ZFSStorageVolume",
)

ZFS_STORAGE_READ_ONLY_REASON = "ZFS storage is managed outside SoAI."


@dataclass(frozen=True, slots=True)
class Partition:
    name: str
    path: str
    size_bytes: int
    filesystem: str | None
    uuid: str | None
    label: str | None
    mount_point: str | None
    partition_table_label: str | None = None
    storage_backend: Literal["block", "zfs"] = "block"
    read_only: bool = False
    read_only_reason: str | None = None
    unmount_allowed: bool = False
    unmount_block_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BlockDevice:
    name: str
    path: str
    size_bytes: int
    device_type: str
    filesystem: str | None
    uuid: str | None
    label: str | None
    mount_point: str | None
    model: str | None
    serial: str | None
    rotational: bool | None
    fingerprint: str
    has_mounted_filesystems: bool
    partitions: tuple[Partition, ...]
    partition_table_type: str | None = None
    storage_backend: Literal["block", "zfs"] = "block"
    read_only: bool = False
    read_only_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ZFSStorageVolume:
    name: str
    source: str
    mount_point: str
    size_bytes: int
    used_bytes: int
    free_bytes: int
    filesystem: str = "zfs"
    storage_backend: Literal["block", "zfs"] = "zfs"
    read_only: bool = True
    read_only_reason: str = ZFS_STORAGE_READ_ONLY_REASON


@dataclass(frozen=True, slots=True)
class PartitionConfig:
    start: str
    end: str
    partition_name: str | None = None


@dataclass(frozen=True, slots=True)
class StorageStatusSnapshot:
    block_devices: tuple[BlockDevice, ...]
    zfs_volumes: tuple[ZFSStorageVolume, ...] = ()
    timestamp_ms: int = field(default_factory=epoch_ms)


@dataclass(frozen=True, slots=True)
class FstabEntry:
    source: str
    uuid: str | None
    mount_point: str
    filesystem: str
    options: str
    dump: int
    pass_num: int


@dataclass(frozen=True, slots=True)
class FstabEntryConfig:
    uuid: str
    mount_point: str
    filesystem: str
    options: str = "defaults"
    dump: int = 0
    pass_num: int = 2
