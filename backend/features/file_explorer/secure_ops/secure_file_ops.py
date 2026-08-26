"""SoAI - TOCTOU-safe file operations using file descriptors [backend/features/file_explorer/secure_ops/secure_file_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.temp_files import create_secure_temp_file_descriptor
from core.filesystem.atomic_write_primitives import fsync_directory
from core.logging.trace import get_logger
from features.file_explorer.secure_ops.fd_ops import open_directory_fd
from features.file_explorer.secure_ops.secure_file_ops_mutations import (
    copy_directory,
    copy_file,
    create_directory,
    move_entry,
    remove_directory_recursive,
    remove_file,
)
from features.file_explorer.secure_ops.secure_read_ops import (
    read_bytes_sample,
    read_text_file,
)
from features.file_explorer.secure_ops.secure_text_writes import (
    write_text_no_symlink_atomic,
)
from features.file_explorer.secure_ops.temp_dir_policy import (
    is_same_filesystem_directory,
)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = ("SecureFileOps",)

LOGGER_NAME = "SoAI.features.file_explorer.secure_file_ops"
OPERATION = "file_explorer.write_text_atomic"


class SecureFileOps:
    __slots__ = ("_allow_symlinks",)

    def __init__(self, *, allow_symlinks: bool) -> None:
        self._allow_symlinks = allow_symlinks

    def list_directory(self, real_path: str) -> list[str]:
        if os.name == "nt":
            if not os.path.isdir(real_path):
                raise NotFoundError(
                    f"Directory not found: '{os.path.basename(real_path)}'.",
                    operation="file_explorer.list_directory",
                )
            return os.listdir(real_path)
        dir_fd = open_directory_fd(real_path)
        try:
            return os.listdir(dir_fd)
        finally:
            os.close(dir_fd)

    def stat_entry(self, directory_path: str, entry_name: str) -> os.stat_result:
        if os.name == "nt":
            full_path = os.path.join(directory_path, entry_name)
            try:
                return os.stat(full_path, follow_symlinks=self._allow_symlinks)
            except FileNotFoundError as exception:
                raise NotFoundError(
                    f"Entry '{entry_name}' not found.",
                    operation="file_explorer.stat_entry",
                ) from exception
        dir_fd = open_directory_fd(directory_path)
        try:
            return os.stat(
                entry_name,
                dir_fd=dir_fd,
                follow_symlinks=self._allow_symlinks,
            )
        except FileNotFoundError as exception:
            raise NotFoundError(
                f"Entry '{entry_name}' not found.",
                operation="file_explorer.stat_entry",
            ) from exception
        finally:
            os.close(dir_fd)

    def stat_path(self, real_path: str) -> os.stat_result:
        try:
            return os.stat(real_path, follow_symlinks=self._allow_symlinks)
        except FileNotFoundError as exception:
            raise NotFoundError(
                f"Path not found: '{os.path.basename(real_path)}'.",
                operation="file_explorer.stat_path",
            ) from exception

    def read_text(self, real_path: str, *, max_bytes: int) -> str:
        return read_text_file(real_path, max_bytes=max_bytes, allow_symlinks=self._allow_symlinks)

    def read_bytes_sample(self, real_path: str, *, max_bytes: int) -> bytes:
        return read_bytes_sample(
            real_path,
            max_bytes=max_bytes,
            allow_symlinks=self._allow_symlinks,
        )

    def _cleanup_temp_file(self, temp_path: str) -> None:
        try:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
        except OSError as cleanup_exception:
            get_logger(LOGGER_NAME).debug(
                "Non-critical: failed to remove temp file during cleanup: %s",
                str(cleanup_exception),
            )

    def write_text_atomic(
        self,
        real_path: str,
        content: str,
        *,
        temp_dir: str,
        root_path: str,
    ) -> None:
        if os.name != "nt" and not self._allow_symlinks:
            write_text_no_symlink_atomic(root_path, real_path, content)
            return
        logger = get_logger(LOGGER_NAME)
        parent_dir = os.path.dirname(real_path)
        encoded = content.encode("utf-8")
        existing_mode: int | None = None
        try:
            stat_info = os.lstat(real_path)
            if stat.S_ISREG(stat_info.st_mode):
                existing_mode = stat.S_IMODE(stat_info.st_mode)
        except FileNotFoundError:
            existing_mode = None
        except OSError:
            existing_mode = None
        target_temp_dir = parent_dir
        if temp_dir and os.path.isdir(temp_dir):
            try:
                if is_same_filesystem_directory(temp_dir, parent_dir):
                    target_temp_dir = temp_dir
            except OSError:
                target_temp_dir = parent_dir
        fd = -1
        temp_path = ""
        try:
            fd, temp_path = create_secure_temp_file_descriptor(
                directory=target_temp_dir,
                prefix=".soai_fe_.",
            )
            if existing_mode is not None:
                os.chmod(temp_path, existing_mode)
            offset = 0
            while offset < len(encoded):
                written = os.write(fd, encoded[offset:])
                if written <= 0:
                    raise OSError("Failed to write file content.")
                offset += written
            os.fsync(fd)
        except RECOVERABLE_EXCEPTIONS as exception:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError as close_exception:
                    logger.debug(
                        "Non-critical: failed to close temp file descriptor during error cleanup: %s",
                        str(close_exception),
                    )
                fd = -1
            self._cleanup_temp_file(temp_path)
            coerced = coerce_to_soai_error(
                exception,
                operation="file_explorer.write_text_atomic",
            )
            log_exception(
                logger,
                coerced,
                message="Failed to write temporary file",
                operation=OPERATION,
            )
            raise coerced from exception
        finally:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError as close_exception:
                    logger.debug(
                        "Non-critical: failed to close temp file descriptor: %s",
                        str(close_exception),
                    )
        try:
            os.replace(temp_path, real_path)
            fsync_directory(parent_dir)
        except RECOVERABLE_EXCEPTIONS as exception:
            self._cleanup_temp_file(temp_path)
            coerced = coerce_to_soai_error(
                exception,
                operation="file_explorer.write_text_atomic",
            )
            log_exception(
                logger,
                coerced,
                message="Failed to atomically write file",
                operation=OPERATION,
            )
            raise coerced from exception

    def create_directory(self, real_path: str) -> None:
        create_directory(real_path)

    def remove_file(self, real_path: str) -> None:
        remove_file(real_path, allow_symlinks=self._allow_symlinks)

    def remove_directory_recursive(self, real_path: str) -> None:
        remove_directory_recursive(real_path)

    def move_entry(self, source_path: str, destination_path: str) -> None:
        move_entry(source_path, destination_path)

    def copy_file(
        self,
        source_path: str,
        destination_path: str,
        *,
        write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
    ) -> None:
        copy_file(
            source_path,
            destination_path,
            allow_symlinks=self._allow_symlinks,
            write_reservation=write_reservation,
        )

    def copy_directory(
        self,
        source_path: str,
        destination_path: str,
        *,
        write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
    ) -> None:
        copy_directory(
            source_path,
            destination_path,
            allow_symlinks=self._allow_symlinks,
            write_reservation=write_reservation,
        )
