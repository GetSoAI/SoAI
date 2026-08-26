"""SoAI - Secure file copy helpers (no symlinks) [backend/app/backup/copy_no_symlinks/file_copy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import stat
from typing import TYPE_CHECKING

from app.backup.copy_no_symlinks.deadlines import check_deadline
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import SecurityError, StateError, ValidationError
from core.files.temp_files import create_secure_temp_file_descriptor
from core.filesystem.file_sync import flush_and_fsync_file
from core.hardware.reserved_writes import write_reserved_bytes
from core.logging.trace import get_logger
from files.archive import sync_raise_if_symlink

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = (
    "sync_copy_file_and_hash_no_symlinks",
    "sync_copy_file_no_symlinks",
)

LOGGER_NAME = "SoAI.app.backup.file_copy"
BACKUP_FILE_COPY_BUFFER_BYTES = MIB_BYTES


def _sync_copy_file_secure(
    source_path: str,
    destination_path: str | None,
    *,
    deadline_monotonic: float | None,
    compute_hash: bool,
    write_reservation: DiskSpaceReservationLeaseProtocol | None,
) -> tuple[int, str | None]:
    logger = get_logger(LOGGER_NAME)
    if not isinstance(source_path, str) or not source_path.strip():
        raise ValidationError("source_path is required.")
    if destination_path is not None and (
        not isinstance(destination_path, str) or not destination_path.strip()
    ):
        raise ValidationError("destination_path must be a non-empty string when provided.")
    sync_raise_if_symlink(source_path, context="file copy source")

    destination_parent = None
    if destination_path is not None:
        destination_parent = os.path.dirname(destination_path)
        if destination_parent:
            os.makedirs(destination_parent, mode=0o700, exist_ok=True)

    read_flags = os.O_RDONLY
    try:
        o_nofollow_flag = os.O_NOFOLLOW
    except AttributeError:
        o_nofollow_flag = None
    if o_nofollow_flag is not None:
        read_flags |= o_nofollow_flag

    source_fd: int | None = None
    source_handle = None
    temp_fd: int | None = None
    temp_path: str | None = None
    try:
        source_fd = os.open(source_path, read_flags)
        stat_info = os.fstat(source_fd)
        if not stat.S_ISREG(stat_info.st_mode):
            raise ValidationError(f"Expected a regular file at {source_path}.")
        source_handle = os.fdopen(source_fd, "rb", buffering=0)
        source_fd = None

        hasher = hashlib.sha256() if compute_hash else None
        total_bytes = 0

        destination_handle = None
        if destination_path is not None:
            dest_dir = destination_parent or os.path.dirname(destination_path)
            temp_fd, temp_path = create_secure_temp_file_descriptor(
                directory=dest_dir or None,
                prefix=f".tmp.{os.getpid()}.",
            )
            destination_handle = os.fdopen(temp_fd, "wb")
            temp_fd = None
        else:
            destination_handle = None
        try:
            buffer_size = BACKUP_FILE_COPY_BUFFER_BYTES
            while True:
                check_deadline(deadline_monotonic, context=f"file_copy:{source_path}")
                data = source_handle.read(buffer_size)
                if not data:
                    break
                if destination_handle is not None:
                    write_reserved_bytes(
                        destination_handle,
                        data,
                        reservation=write_reservation,
                    )
                if hasher is not None:
                    hasher.update(data)
                total_bytes += len(data)
            if destination_handle is not None:
                flush_and_fsync_file(destination_handle)
        finally:
            if destination_handle is not None:
                try:
                    destination_handle.close()
                except OSError:
                    logger.debug("Failed to close destination handle for %s", temp_path)

        if destination_path is not None:
            if temp_path is None:
                raise StateError("Secure copy failed to produce a temp file.")
            os.replace(temp_path, destination_path)
            temp_path = None
        digest = hasher.hexdigest() if hasher is not None else None
        return (total_bytes, digest)
    except (OSError, RuntimeError, ValueError) as exception:
        raise StateError(f"File copy failed: {exception}") from exception
    finally:
        if source_handle is not None:
            try:
                source_handle.close()
            except OSError:
                logger.debug("Failed to close source handle for %s", source_path)
        if source_fd is not None:
            try:
                os.close(source_fd)
            except OSError:
                logger.debug("Failed to close source fd for %s", source_path)
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                logger.debug("Failed to close temp fd for %s", temp_path)
        if temp_path is not None:
            try:
                os.remove(temp_path)
            except OSError:
                logger.debug("Failed to remove temp file: %s", temp_path)


def sync_copy_file_no_symlinks(
    source_path: str,
    destination_path: str | None,
    *,
    deadline_monotonic: float | None = None,
    write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
) -> tuple[int, str | None]:
    return _sync_copy_file_secure(
        source_path,
        destination_path,
        deadline_monotonic=deadline_monotonic,
        compute_hash=False,
        write_reservation=write_reservation,
    )


def sync_copy_file_and_hash_no_symlinks(
    source_path: str,
    destination_path: str | None,
    *,
    deadline_monotonic: float | None = None,
    write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
) -> tuple[int, str]:
    size, file_hash = _sync_copy_file_secure(
        source_path,
        destination_path,
        deadline_monotonic=deadline_monotonic,
        compute_hash=True,
        write_reservation=write_reservation,
    )
    if not isinstance(file_hash, str) or not file_hash:
        raise SecurityError("Failed to compute hash while copying file.")
    return size, file_hash
