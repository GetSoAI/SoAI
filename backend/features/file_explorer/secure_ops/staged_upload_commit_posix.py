"""SoAI - POSIX staged upload commit primitives [backend/features/file_explorer/secure_ops/staged_upload_commit_posix.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import os
import stat
import uuid
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.hardware.reservation_claims import claim_reserved_write
from features.file_explorer.secure_ops import (
    staged_upload_commit_outcomes,
    staged_upload_copy_io,
)
from features.file_explorer.secure_ops.staged_upload_destination import (
    fsync_destination_directory,
    open_pinned_destination_directory,
    rollback_destination_entry,
)
from features.file_explorer.secure_ops.staged_upload_source import (
    OpenedStagedSource,
    close_staged_source,
    open_staged_source,
    remove_staged_source,
    same_staged_file_identity,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("commit_posix_staged_upload",)

_COPY_CHUNK_BYTES = 8 * 1024 * 1024


def commit_posix_staged_upload(
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
    destination_name = os.path.basename(destination_path)
    destination_descriptor = open_pinned_destination_directory(
        destination_root,
        destination_parent,
        allow_symlinks=allow_symlinks,
    )
    try:
        source = open_staged_source(source_path, expected_size=expected_size)
        try:
            staged_upload_commit_outcomes.raise_if_cancelled(token)
            try:
                _link_staged_source(source, destination_name, destination_descriptor)
            except FileExistsError as exception:
                raise staged_upload_commit_outcomes.destination_exists_error(
                    exception
                ) from exception
            except OSError as exception:
                if exception.errno in {errno.EEXIST, errno.EISDIR}:
                    raise staged_upload_commit_outcomes.destination_exists_error(
                        exception
                    ) from exception
                if not _is_fallback_link_error(exception.errno):
                    raise
                _copy_fallback(
                    source=source,
                    source_path=source_path,
                    destination_path=destination_path,
                    destination_parent=destination_parent,
                    destination_name=destination_name,
                    destination_descriptor=destination_descriptor,
                    token=token,
                    storage_manager=storage_manager,
                )
                return
            _finish_hard_link_commit(
                source=source,
                source_path=source_path,
                destination_path=destination_path,
                destination_name=destination_name,
                destination_descriptor=destination_descriptor,
                token=token,
            )
        finally:
            close_staged_source(source)
    finally:
        os.close(destination_descriptor)


def _link_staged_source(
    source: OpenedStagedSource,
    destination_name: str,
    destination_descriptor: int,
) -> None:
    os.link(
        source.filename,
        destination_name,
        src_dir_fd=source.parent_descriptor,
        dst_dir_fd=destination_descriptor,
        follow_symlinks=False,
    )
    link_validated = False
    try:
        destination_stat = os.stat(
            destination_name,
            dir_fd=destination_descriptor,
            follow_symlinks=False,
        )
        if not same_staged_file_identity(destination_stat, source.stat_result):
            raise StateError("Staged upload source changed during commit.")
        link_validated = True
    finally:
        if not link_validated:
            rollback_destination_entry(destination_name, destination_descriptor)


def _finish_hard_link_commit(
    *,
    source: OpenedStagedSource,
    source_path: str,
    destination_path: str,
    destination_name: str,
    destination_descriptor: int,
    token: CancellationTokenProtocol,
) -> None:
    source_removed = False
    try:
        fsync_destination_directory(destination_descriptor)
        remove_staged_source(source)
        source_removed = True
    finally:
        if not source_removed:
            rollback_destination_entry(destination_name, destination_descriptor)
    staged_upload_commit_outcomes.raise_if_commit_cancelled(token, source_path, destination_path)


def _copy_fallback(
    *,
    source: OpenedStagedSource,
    source_path: str,
    destination_path: str,
    destination_parent: str,
    destination_name: str,
    destination_descriptor: int,
    token: CancellationTokenProtocol,
    storage_manager: StorageManagerProtocol,
) -> None:
    reservation = storage_manager.reserve_disk_space(
        path=destination_parent,
        required_bytes=source.stat_result.st_size,
        operation="file_explorer.upload.commit_copy",
        details={"size_bytes": source.stat_result.st_size},
    )
    partial_name = f".soai-upload-{uuid.uuid4().hex}.partial"
    partial_descriptor = -1
    committed = False
    operation_completed = False
    release_attempted = False
    try:
        partial_descriptor = os.open(
            partial_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            stat.S_IMODE(source.stat_result.st_mode),
            dir_fd=destination_descriptor,
        )
        os.lseek(source.file_descriptor, 0, os.SEEK_SET)
        while True:
            staged_upload_commit_outcomes.raise_if_cancelled(token)
            chunk = os.read(source.file_descriptor, _COPY_CHUNK_BYTES)
            if not chunk:
                break
            with claim_reserved_write(reservation, size_bytes=len(chunk)):
                staged_upload_copy_io.write_all(partial_descriptor, chunk)
        os.fsync(partial_descriptor)
        os.close(partial_descriptor)
        partial_descriptor = -1
        staged_upload_commit_outcomes.raise_if_cancelled(token)
        _commit_partial_no_overwrite(partial_name, destination_name, destination_descriptor)
        committed = True
        os.unlink(partial_name, dir_fd=destination_descriptor)
        partial_name = ""
        fsync_destination_directory(destination_descriptor)
        release_attempted = True
        reservation.release()
        remove_staged_source(source)
        operation_completed = True
    finally:
        try:
            try:
                if committed and not operation_completed:
                    rollback_destination_entry(destination_name, destination_descriptor)
            finally:
                try:
                    if partial_descriptor >= 0:
                        os.close(partial_descriptor)
                finally:
                    if partial_name:
                        _remove_partial_if_present(partial_name, destination_descriptor)
        finally:
            if not release_attempted:
                reservation.release()
    staged_upload_commit_outcomes.raise_if_commit_cancelled(token, source_path, destination_path)


def _commit_partial_no_overwrite(
    partial_name: str,
    destination_name: str,
    destination_descriptor: int,
) -> None:
    try:
        os.link(
            partial_name,
            destination_name,
            src_dir_fd=destination_descriptor,
            dst_dir_fd=destination_descriptor,
            follow_symlinks=False,
        )
    except FileExistsError as exception:
        raise staged_upload_commit_outcomes.destination_exists_error(exception) from exception


def _remove_partial_if_present(partial_name: str, destination_descriptor: int) -> bool:
    try:
        os.unlink(partial_name, dir_fd=destination_descriptor)
        return True
    except FileNotFoundError:
        return False


def _is_fallback_link_error(error_number: int | None) -> bool:
    return error_number in (
        errno.EXDEV,
        errno.EPERM,
        errno.EOPNOTSUPP,
        errno.ENOTSUP,
        errno.ENOSYS,
    )
