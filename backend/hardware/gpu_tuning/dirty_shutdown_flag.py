"""SoAI - GPU tuning dirty shutdown flag lifecycle [backend/hardware/gpu_tuning/dirty_shutdown_flag.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.errors.exceptions import ValidationError
from core.files.file_identity import FileIdentity
from core.files.operations import async_remove
from core.filesystem.async_queries import async_path_exists
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.atomic_writes import atomic_create_text_content_exclusive
from core.filesystem.open_files import open_regular_file_descriptor_no_symlink
from core.filesystem.path_coercion import coerce_path, normalize_filesystem_path
from core.hardware.gpu_control_types import (
    GPUControlDirtyMarkerReceipt,
    GPUSlotReadError,
    GPUSlotReadFailure,
    GPUSlotReadResult,
    GPUSlotReadState,
)
from core.logging.protocols import TraceLogger
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_tuning.startup_scope_types import GPUStartupScopePolicy

__all__ = (
    "clear_dirty_shutdown_flag_file",
    "establish_gpu_dirty_marker_receipt",
    "observe_gpu_startup_marker_policy",
    "require_gpu_marker_store_read",
    "remove_gpu_startup_marker",
)


def establish_gpu_dirty_marker_receipt(
    path: str, previous: GPUControlDirtyMarkerReceipt | None
) -> GPUControlDirtyMarkerReceipt:
    require_canonical_trimmed_json_text(path, error_message="GPU dirty marker path is invalid.")
    coerce_path(path)
    if previous is not None and (
        not isinstance(previous, GPUControlDirtyMarkerReceipt) or previous.marker_path != path
    ):
        raise ValidationError("GPU dirty marker receipt belongs to another authority.")
    resolved = normalize_filesystem_path(path)
    try:
        os.lstat(resolved)
    except FileNotFoundError:
        atomic_create_text_content_exclusive(
            path, "", encoding="utf-8", errors="strict", ensure_parent=False, fsync=True
        )
    descriptor = open_regular_file_descriptor_no_symlink(resolved, writable=os.name == "nt")
    try:
        original = _require_empty_marker(descriptor, resolved)
        os.fsync(descriptor)
        fsync_directory(os.path.dirname(resolved) or ".", strict=True)
        observed = _require_empty_marker(descriptor, resolved)
        if (
            observed.st_dev != original.st_dev
            or observed.st_ino != original.st_ino
            or observed.st_mtime_ns != original.st_mtime_ns
            or observed.st_ctime_ns != original.st_ctime_ns
        ):
            raise ValidationError("GPU dirty marker changed during synchronization.")
        return GPUControlDirtyMarkerReceipt(path, observed.st_dev, observed.st_ino)
    finally:
        os.close(descriptor)


def _require_empty_marker(descriptor: int, path: str) -> os.stat_result:
    observed, located = os.fstat(descriptor), os.lstat(path)
    regular_empty_marker = (
        stat.S_ISREG(observed.st_mode)
        and stat.S_ISREG(located.st_mode)
        and observed.st_size == 0
        and located.st_size == 0
    )
    descriptor_matches_location = FileIdentity.from_stat(observed) == FileIdentity.from_stat(
        located
    )
    if not regular_empty_marker or not descriptor_matches_location:
        raise ValidationError("GPU dirty marker must remain the same empty regular file.")
    os.lseek(descriptor, 0, os.SEEK_SET)
    if os.read(descriptor, 1) != b"":
        raise ValidationError("GPU dirty marker contains unexpected content.")
    return observed


async def clear_dirty_shutdown_flag_file(path: str, logger: TraceLogger) -> None:
    if await async_path_exists(path):
        establish_gpu_dirty_marker_receipt(path, None)
        logger.trace("Clean shutdown detected. Removing GPU settings dirty flag.")
        await async_remove(path)
        fsync_directory(os.path.dirname(normalize_filesystem_path(path)) or ".", strict=True)


def remove_gpu_startup_marker(path: str) -> None:
    require_canonical_trimmed_json_text(path, error_message="GPU dirty marker path is invalid.")
    resolved = normalize_filesystem_path(path)
    parent = os.path.dirname(resolved) or "."
    try:
        os.lstat(resolved)
    except FileNotFoundError:
        fsync_directory(parent, strict=True)
        return
    receipt = establish_gpu_dirty_marker_receipt(path, None)
    observed = os.lstat(resolved)
    if observed.st_dev != receipt.file_device or observed.st_ino != receipt.file_inode:
        raise ValidationError("GPU startup marker changed before removal.")
    os.unlink(resolved)
    fsync_directory(parent, strict=True)
    try:
        os.lstat(resolved)
    except FileNotFoundError:
        return
    raise ValidationError("GPU startup marker reappeared during completion.")


def observe_gpu_startup_marker_policy(
    path: str,
    previous_policy: GPUStartupScopePolicy | None,
    live_receipt: GPUControlDirtyMarkerReceipt | None,
) -> GPUStartupScopePolicy:
    require_canonical_trimmed_json_text(path, error_message="GPU dirty marker path is invalid.")
    coerce_path(path)
    if live_receipt is not None and (
        not isinstance(live_receipt, GPUControlDirtyMarkerReceipt)
        or live_receipt.marker_path != path
    ):
        raise ValidationError("GPU live marker receipt belongs to another authority.")
    try:
        observed = os.lstat(path)
    except FileNotFoundError:
        if previous_policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL:
            return previous_policy
        return GPUStartupScopePolicy.RECORDED_RECOVERY
    except OSError as exception:
        raise GPUSlotReadError(GPUSlotReadFailure.UNAVAILABLE) from exception
    certified_live_empty_marker = (
        live_receipt is not None
        and stat.S_ISREG(observed.st_mode)
        and observed.st_size == 0
        and observed.st_dev == live_receipt.file_device
        and observed.st_ino == live_receipt.file_inode
    )
    if (
        previous_policy != GPUStartupScopePolicy.RECORDED_RECOVERY
        or not certified_live_empty_marker
    ):
        return GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL
    return previous_policy


def require_gpu_marker_store_read(
    read: GPUSlotReadResult, *, marker_path: str, pending_devices: tuple[str, ...]
) -> None:
    if read.state != GPUSlotReadState.ABSENT:
        return
    if pending_devices:
        raise GPUSlotReadError(GPUSlotReadFailure.UNAVAILABLE)
    try:
        os.lstat(marker_path)
    except FileNotFoundError:
        return
    except OSError as exception:
        raise GPUSlotReadError(GPUSlotReadFailure.UNAVAILABLE) from exception
    raise GPUSlotReadError(GPUSlotReadFailure.UNAVAILABLE)
