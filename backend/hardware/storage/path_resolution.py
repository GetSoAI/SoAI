"""SoAI - Storage path resolution utilities [backend/hardware/storage/path_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil

import psutil

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.path_policy import ensure_path_within_base_lexical
from core.hardware.speed_test.disk_speed_test_measurement import resolve_existing_path
from core.logging.trace import get_logger

__all__ = (
    "collect_disk_free_bytes",
    "resolve_mount_point",
    "resolve_storage_path",
)

LOGGER_NAME = "SoAI.hardware.storage.path_resolution"
OPERATION_HARDWARE_STORAGE_RESOLVE_MOUNT_POINT_COMPARE = (
    "hardware_storage.resolve_mount_point.compare"
)
OPERATION_HARDWARE_STORAGE_RESOLVE_MOUNT_POINT_LIST_PARTITIONS = (
    "hardware_storage.resolve_mount_point.list_partitions"
)


def resolve_storage_path(models_dir: str | None) -> str | None:
    if not isinstance(models_dir, str):
        return None
    trimmed = models_dir.strip()
    if not trimmed:
        return None
    resolved = resolve_existing_path(trimmed)
    if not resolved:
        return None
    if os.path.isdir(resolved):
        return resolved
    parent = os.path.dirname(resolved)
    return parent or None


def collect_disk_free_bytes(storage_path: str | None) -> int | None:
    if not storage_path:
        return None
    try:
        usage = shutil.disk_usage(storage_path)
    except OSError:
        return None
    try:
        free_value = usage.free
    except AttributeError:
        free_value = None
    try:
        return int(free_value) if free_value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def resolve_mount_point(path: str) -> str | None:
    logger = get_logger(LOGGER_NAME)
    if not path.strip():
        return None
    normalized_path = os.path.abspath(path)
    drive, _tail = os.path.splitdrive(normalized_path)
    if drive:
        return drive + os.sep
    best_match: str | None = None
    try:
        partitions = psutil.disk_partitions(all=True)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to list disk partitions (non-critical).",
            operation=OPERATION_HARDWARE_STORAGE_RESOLVE_MOUNT_POINT_LIST_PARTITIONS,
            level="debug",
        )
        partitions = []
    for partition in partitions:
        try:
            mountpoint = partition.mountpoint
        except AttributeError:
            mountpoint = None
        if not isinstance(mountpoint, str) or not mountpoint:
            continue
        try:
            ensure_path_within_base_lexical(
                mountpoint,
                normalized_path,
                description="Storage path",
            )
            if best_match is None or len(mountpoint) > len(best_match):
                best_match = mountpoint
        except ValueError:
            continue
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to compare mountpoint candidate (non-critical).",
                operation=OPERATION_HARDWARE_STORAGE_RESOLVE_MOUNT_POINT_COMPARE,
                details={"normalized_path": normalized_path, "mountpoint": mountpoint},
                level="trace",
            )
            continue
    return best_match
