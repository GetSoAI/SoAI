"""SoAI - Windows staged upload commit primitives [backend/features/file_explorer/secure_ops/staged_upload_commit_windows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import os
import stat
import uuid
from typing import TYPE_CHECKING

from core.errors.exceptions import SecurityError, StateError, ValidationError
from core.files.windows_reparse_points import is_windows_reparse_point
from core.filesystem.atomic_write_primitives import fsync_directory
from core.hardware.reservation_claims import claim_reserved_write
from features.file_explorer.secure_ops import (
    staged_upload_commit_outcomes,
    staged_upload_copy_io,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("commit_windows_staged_upload",)

_COPY_CHUNK_BYTES = 8 * 1024 * 1024
_WINDOWS_BINARY_OPEN_FLAG = 0x8000


def commit_windows_staged_upload(
    *,
    source_path: str,
    destination_path: str,
    destination_root: str,
    expected_size: int,
    token: CancellationTokenProtocol,
    storage_manager: StorageManagerProtocol,
    allow_symlinks: bool,
) -> None:
    destination_parent = os.path.dirname(destination_path)
    source_stat = os.stat(source_path, follow_symlinks=False)
    if not allow_symlinks and _is_reparse_point(source_path, source_stat):
        raise SecurityError("Staged upload source cannot be a reparse point.")
    if not allow_symlinks:
        _reject_reparse_directory_chain(destination_root, os.path.dirname(destination_path))
    if not stat.S_ISREG(source_stat.st_mode):
        raise ValidationError("Staged upload source must be a regular file.")
    if source_stat.st_size != expected_size:
        raise StateError("Staged upload source size changed before commit.")
    staged_upload_commit_outcomes.raise_if_cancelled(token)
    try:
        os.rename(source_path, destination_path)
    except FileExistsError as exception:
        raise staged_upload_commit_outcomes.destination_exists_error(exception) from exception
    except OSError as exception:
        if exception.errno != errno.EXDEV:
            raise
        _copy_fallback(
            source_path=source_path,
            destination_path=destination_path,
            source_stat=source_stat,
            token=token,
            storage_manager=storage_manager,
        )
        return
    commit_validated = False
    try:
        destination_stat = os.stat(destination_path, follow_symlinks=False)
        if not _same_file_identity(destination_stat, source_stat):
            raise StateError("Staged upload source changed during commit.")
        fsync_directory(destination_parent, strict=True)
        commit_validated = True
    finally:
        if not commit_validated:
            os.rename(destination_path, source_path)
            fsync_directory(destination_parent, strict=True)
    staged_upload_commit_outcomes.raise_if_commit_cancelled(token, source_path, destination_path)


def _copy_fallback(
    *,
    source_path: str,
    destination_path: str,
    source_stat: os.stat_result,
    token: CancellationTokenProtocol,
    storage_manager: StorageManagerProtocol,
) -> None:
    destination_parent = os.path.dirname(destination_path)
    reservation = storage_manager.reserve_disk_space(
        path=destination_parent,
        required_bytes=source_stat.st_size,
        operation="file_explorer.upload.commit_copy",
        details={"size_bytes": source_stat.st_size},
    )
    partial_path = os.path.join(
        destination_parent,
        f".soai-upload-{uuid.uuid4().hex}.partial",
    )
    committed = False
    operation_completed = False
    release_attempted = False
    try:
        source_descriptor = os.open(source_path, os.O_RDONLY | _WINDOWS_BINARY_OPEN_FLAG)
        try:
            partial_descriptor = os.open(
                partial_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _WINDOWS_BINARY_OPEN_FLAG,
                stat.S_IMODE(source_stat.st_mode),
            )
            try:
                while True:
                    staged_upload_commit_outcomes.raise_if_cancelled(token)
                    chunk = os.read(source_descriptor, _COPY_CHUNK_BYTES)
                    if not chunk:
                        break
                    with claim_reserved_write(reservation, size_bytes=len(chunk)):
                        staged_upload_copy_io.write_all(partial_descriptor, chunk)
                os.fsync(partial_descriptor)
            finally:
                os.close(partial_descriptor)
        finally:
            os.close(source_descriptor)
        staged_upload_commit_outcomes.raise_if_cancelled(token)
        try:
            os.rename(partial_path, destination_path)
        except FileExistsError as exception:
            raise staged_upload_commit_outcomes.destination_exists_error(exception) from exception
        committed = True
        fsync_directory(destination_parent, strict=True)
        release_attempted = True
        reservation.release()
        current_stat = os.stat(source_path, follow_symlinks=False)
        if not _same_file_identity(current_stat, source_stat):
            raise StateError("Staged upload source changed during commit.")
        os.unlink(source_path)
        operation_completed = True
    finally:
        try:
            if committed and not operation_completed:
                os.unlink(destination_path)
                fsync_directory(destination_parent, strict=True)
        finally:
            try:
                _remove_partial_if_present(partial_path)
            finally:
                if not release_attempted:
                    reservation.release()
    staged_upload_commit_outcomes.raise_if_commit_cancelled(token, source_path, destination_path)


def _is_reparse_point(path: str, path_stat: os.stat_result) -> bool:
    if os.path.islink(path):
        return True
    return is_windows_reparse_point(path_stat)


def _reject_reparse_directory_chain(root_path: str, directory_path: str) -> None:
    root = os.path.abspath(root_path)
    current = root
    root_stat = os.stat(root, follow_symlinks=False)
    if _is_reparse_point(root, root_stat):
        raise SecurityError("Upload destination contains a reparse point.")
    relative = os.path.relpath(os.path.abspath(directory_path), root)
    if relative == ".":
        return
    for path_component in relative.split(os.sep):
        current = os.path.join(current, path_component)
        current_stat = os.stat(current, follow_symlinks=False)
        if _is_reparse_point(current, current_stat):
            raise SecurityError("Upload destination contains a reparse point.")


def _same_file_identity(first: os.stat_result, second: os.stat_result) -> bool:
    return (
        first.st_dev == second.st_dev
        and first.st_ino == second.st_ino
        and first.st_size == second.st_size
    )


def _remove_partial_if_present(partial_path: str) -> bool:
    try:
        os.unlink(partial_path)
        return True
    except FileNotFoundError:
        return False
