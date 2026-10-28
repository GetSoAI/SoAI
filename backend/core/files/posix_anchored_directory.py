"""SoAI - Descriptor anchored POSIX directory mutation [backend/core/files/posix_anchored_directory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import os
import stat
import sys

from core.errors.exceptions import StateError
from core.files.commit_receipt import FileCleanupIncompleteError
from core.files.managed_storage_traversal import close_file_descriptor_stack
from core.files.secure_open_flags import secure_read_only_open_flags
from core.files.workspace_descriptor import open_workspace_directory_fd
from core.filesystem.descriptor_io import (
    open_descriptor,
    read_exclusive_regular_descriptor,
    write_all_descriptor_bytes,
)
from core.filesystem.exclusive_rename import rename_file_without_replacement
from core.filesystem.path_coercion import require_direct_entry_name

__all__ = ("PosixAnchoredDirectory", "open_posix_anchored_directory")


class PosixAnchoredDirectory:
    def __init__(self, descriptor: int) -> None:
        self._descriptor = descriptor

    @property
    def identity(self) -> tuple[int, int]:
        information = os.fstat(self._descriptor)
        if not stat.S_ISDIR(information.st_mode):
            raise StateError("Anchored workspace is not a directory.")
        return information.st_dev, information.st_ino

    def close(self) -> None:
        descriptor = self._descriptor
        self._descriptor = -1
        if descriptor >= 0:
            close_file_descriptor_stack([descriptor])

    def open_directory(self, name: str) -> PosixAnchoredDirectory:
        try:
            descriptor = open_workspace_directory_fd(
                self._descriptor, require_direct_entry_name(name), error_cls=StateError
            )
        except StateError as exception:
            if isinstance(exception.__cause__, FileNotFoundError):
                raise FileNotFoundError("Anchored workspace directory is missing.") from exception
            raise
        return PosixAnchoredDirectory(descriptor)

    def create_directory(self, name: str) -> PosixAnchoredDirectory:
        os.mkdir(require_direct_entry_name(name), 0o700, dir_fd=self._descriptor)
        descriptor = open_workspace_directory_fd(self._descriptor, name, error_cls=StateError)
        accepted = False
        try:
            os.fchmod(descriptor, 0o700)
            directory = PosixAnchoredDirectory(descriptor)
            accepted = True
            return directory
        finally:
            if not accepted:
                os.close(descriptor)

    def write_file(self, name: str, content: bytes, *, posix_executable: bool = False) -> None:
        descriptor = self.open_file(name, create=True)
        try:
            write_all_descriptor_bytes(
                descriptor, content, error_message="Workspace file write made no progress."
            )
            if posix_executable:
                os.fchmod(descriptor, 0o700)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def open_file(self, name: str, *, create: bool = False, delete: bool = False) -> int:
        _ = delete
        descriptor = open_descriptor(
            require_direct_entry_name(name),
            (
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
                if create
                else secure_read_only_open_flags(directory=False)
            ),
            0o600,
            dir_fd=self._descriptor,
        )
        accepted = False
        try:
            if create:
                os.fchmod(descriptor, 0o600)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise StateError("Anchored workspace entry is not a regular file.")
            accepted = True
            return descriptor
        finally:
            if not accepted:
                primary = sys.exception()
                close_file_descriptor_stack([descriptor], primary_exception=primary)
                if create:
                    raise FileCleanupIncompleteError(
                        "Rejected temporary entry was retained without deletion authority.",
                        details={"retained_names": [name]},
                        cause=primary,
                    ) from primary

    def read_file(
        self, name: str, maximum_bytes: int, *, posix_executable: bool | None = None
    ) -> bytes:
        try:
            descriptor = open_descriptor(
                require_direct_entry_name(name),
                secure_read_only_open_flags(directory=False),
                dir_fd=self._descriptor,
            )
        except OSError as exception:
            if exception.errno == errno.ELOOP:
                raise StateError("Materialized member became a symbolic link.") from exception
            raise
        try:
            if posix_executable is not None and stat.S_IMODE(os.fstat(descriptor).st_mode) != (
                0o700 if posix_executable else 0o600
            ):
                raise StateError("Materialized file access mode changed.")
            return read_exclusive_regular_descriptor(descriptor, maximum_bytes)
        finally:
            os.close(descriptor)

    def names(self) -> tuple[str, ...]:
        names: list[str] = []
        with os.scandir(self._descriptor) as entries:
            for entry in entries:
                if len(names) >= 4096:
                    raise StateError("Workspace directory exceeds the bounded entry inventory.")
                names.append(entry.name)
        return tuple(sorted(names))

    def remove_file(self, name: str) -> None:
        os.unlink(require_direct_entry_name(name), dir_fd=self._descriptor)

    def remove_directory(
        self, name: str, *, expected_identity: tuple[int, int] | None = None
    ) -> None:
        if expected_identity is not None:
            directory = self.open_directory(name)
            try:
                if directory.identity != expected_identity:
                    raise StateError("Anchored cleanup directory identity changed.")
                os.rmdir(require_direct_entry_name(name), dir_fd=self._descriptor)
            finally:
                directory.close()
        else:
            os.rmdir(require_direct_entry_name(name), dir_fd=self._descriptor)

    def publish_directory(self, source: str, destination: str) -> None:
        rename_file_without_replacement(
            require_direct_entry_name(source),
            require_direct_entry_name(destination),
            source_dir_fd=self._descriptor,
            destination_dir_fd=self._descriptor,
        )

    def flush(self) -> None:
        os.fsync(self._descriptor)


def open_posix_anchored_directory(path: str) -> PosixAnchoredDirectory:
    absolute = os.path.abspath(path)
    descriptor = open_workspace_directory_fd(None, os.sep, error_cls=StateError)
    try:
        for segment in absolute.split(os.sep):
            if not segment:
                continue
            child = open_workspace_directory_fd(descriptor, segment, error_cls=StateError)
            os.close(descriptor)
            descriptor = child
        directory = PosixAnchoredDirectory(descriptor)
        descriptor = -1
        return directory
    finally:
        if descriptor >= 0:
            os.close(descriptor)
