"""SoAI - Secure file copy helpers (no symlinks) [backend/app/backup/copy_no_symlinks/file_copy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import stat
import sys
from dataclasses import dataclass
from threading import Event
from typing import TYPE_CHECKING

from app.backup.copy_no_symlinks.deadlines import check_deadline
from core.concurrency.cancellation import check_cancellation_deadline
from core.concurrency.deadlines import MonotonicDeadline
from core.config.byte_sizes import MIB_BYTES
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError, SecurityError, StateError, ValidationError
from core.files.file_identity import FileIdentity
from core.files.managed_file_opening import open_managed_file_descriptor
from core.files.temp_files import create_secure_temp_file_descriptor
from core.filesystem.descriptor_io import open_descriptor
from core.filesystem.file_sync import flush_and_fsync_file
from core.filesystem.path_coercion import normalize_filesystem_path
from core.hardware.reservation_exceptions import preserve_primary_exception_cleanup_failure
from core.hardware.reserved_writes import write_reserved_bytes
from core.logging.trace import get_logger
from files.archive import sync_raise_if_symlink

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = (
    "sync_copy_file_and_hash_no_symlinks",
    "BoundedFileCapture",
    "sync_copy_file_no_symlinks",
)

LOGGER_NAME = "SoAI.app.backup.file_copy"
OPERATION_LOG_CAPTURE_CLOSE = "logs.export.capture.close"
BACKUP_FILE_COPY_BUFFER_BYTES = MIB_BYTES


@dataclass(frozen=True, slots=True)
class BoundedFileCapture:
    source_root: str
    identity: FileIdentity
    byte_count: int
    allow_append: bool
    cancellation_event: Event

    def validate(self, actual: FileIdentity) -> None:
        check_cancellation_deadline(self.cancellation_event, operation="logs.export.capture")
        if self.byte_count != self.identity.size or self.byte_count < 0:
            raise ValidationError("Invalid bounded file capture size.")
        if not actual.is_regular_file or not self.identity.matches_file_object(actual):
            raise ConflictError("Log file was replaced during capture.")
        if actual.size < self.byte_count or (
            not self.allow_append and not self.identity.matches_descriptor_snapshot(actual)
        ):
            raise ConflictError("Log file changed during capture.")


def _sync_copy_file_secure(
    source_path: str,
    destination_path: str | None,
    *,
    deadline_monotonic: float | None,
    compute_hash: bool,
    write_reservation: DiskSpaceReservationLeaseProtocol | None,
    capture: BoundedFileCapture | None = None,
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
            os.makedirs(normalize_filesystem_path(destination_parent), mode=0o700, exist_ok=True)

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
        if capture is None:
            source_fd = open_descriptor(normalize_filesystem_path(source_path), read_flags)
        else:
            source_fd = open_managed_file_descriptor(
                capture.source_root,
                source_path,
                concurrent_leaf_read=True,
            ).descriptor
        stat_info = os.fstat(source_fd)
        if not stat.S_ISREG(stat_info.st_mode):
            raise ValidationError(f"Expected a regular file at {source_path}.")
        if capture is not None:
            capture.validate(FileIdentity.from_stat(stat_info))
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
                if capture is None:
                    check_deadline(deadline_monotonic, context=f"file_copy:{source_path}")
                if capture is not None:
                    check_cancellation_deadline(
                        capture.cancellation_event,
                        (
                            MonotonicDeadline(deadline_monotonic)
                            if deadline_monotonic is not None
                            else None
                        ),
                        operation="logs.export.capture",
                    )
                    if total_bytes == capture.byte_count:
                        break
                read_size = (
                    buffer_size
                    if capture is None
                    else min(buffer_size, capture.byte_count - total_bytes)
                )
                data = source_handle.read(read_size)
                if not data:
                    if capture is not None and total_bytes < capture.byte_count:
                        raise ConflictError("Log file shrank during capture.")
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
            if capture is not None:
                capture.validate(FileIdentity.from_stat(os.fstat(source_handle.fileno())))
            if destination_handle is not None:
                flush_and_fsync_file(destination_handle)
        finally:
            if destination_handle is not None:
                primary_exception = sys.exception()
                try:
                    destination_handle.close()
                except OSError as close_exception:
                    if capture is not None:
                        if primary_exception is not None:
                            log_exception(
                                logger,
                                close_exception,
                                message="Log capture destination closure failed.",
                                operation=OPERATION_LOG_CAPTURE_CLOSE,
                            )
                        preserve_primary_exception_cleanup_failure(
                            primary_exception,
                            close_exception,
                            cleanup_action="Log capture destination closure",
                        )
                    else:
                        logger.debug("Failed to close destination handle for %s", temp_path)

        if capture is not None:
            source_handle.close()
            source_handle = None
            check_cancellation_deadline(
                capture.cancellation_event,
                MonotonicDeadline(deadline_monotonic) if deadline_monotonic is not None else None,
                operation="logs.export.capture",
            )
        if destination_path is not None:
            if temp_path is None:
                raise StateError("Secure copy failed to produce a temp file.")
            os.replace(
                normalize_filesystem_path(temp_path), normalize_filesystem_path(destination_path)
            )
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
                os.remove(normalize_filesystem_path(temp_path))
            except OSError:
                logger.debug("Failed to remove temp file: %s", temp_path)


def sync_copy_file_no_symlinks(
    source_path: str,
    destination_path: str | None,
    *,
    deadline_monotonic: float | None = None,
    write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
    capture: BoundedFileCapture | None = None,
) -> tuple[int, str | None]:
    return _sync_copy_file_secure(
        source_path,
        destination_path,
        deadline_monotonic=deadline_monotonic,
        compute_hash=False,
        write_reservation=write_reservation,
        capture=capture,
    )


def sync_copy_file_and_hash_no_symlinks(
    source_path: str,
    destination_path: str | None,
    *,
    deadline_monotonic: float | None = None,
    write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
    capture: BoundedFileCapture | None = None,
) -> tuple[int, str]:
    size, file_hash = _sync_copy_file_secure(
        source_path,
        destination_path,
        deadline_monotonic=deadline_monotonic,
        compute_hash=True,
        write_reservation=write_reservation,
        capture=capture,
    )
    if not isinstance(file_hash, str) or not file_hash:
        raise SecurityError("Failed to compute hash while copying file.")
    return size, file_hash
