"""SoAI - Handle anchored Windows workspace mutation [backend/core/files/windows_anchored_directory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os
import sys
from functools import partial

from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import StateError
from core.files.windows_directory_operations import (
    flush_windows_directory,
    list_windows_directory,
    open_relative_windows_entry,
    remove_windows_entry,
    windows_directory_identity,
)
from core.files.windows_entry_publication import publish_windows_entry_handle
from core.files.windows_handle_operations import (
    close_windows_path_resources,
    convert_windows_handle_to_file_descriptor,
    windows_handle_from_descriptor,
)
from core.filesystem.descriptor_io import (
    read_exclusive_regular_descriptor,
    write_all_descriptor_bytes,
)
from core.filesystem.exclusive_rename import rename_file_without_replacement
from core.filesystem.path_coercion import normalize_filesystem_path
from core.filesystem.windows_sharing_conflicts import (
    ORDINARY_FILESYSTEM_SECONDS,
    retry_windows_sharing_conflicts,
)
from core.system.windows_ctypes import last_windows_error, load_kernel32

__all__ = ("WindowsAnchoredDirectory", "open_windows_anchored_directory")


class WindowsAnchoredDirectory:
    def __init__(
        self,
        handle: int,
        *,
        ancestor_handles: tuple[int, ...] = (),
        deadline: MonotonicDeadline | None = None,
        cancellation: CancellationTokenProtocol | None = None,
    ) -> None:
        self._handle = handle
        self._ancestor_handles = ancestor_handles
        self._deadline = deadline or deadline_after(ORDINARY_FILESYSTEM_SECONDS)
        self._cancellation = cancellation

    @property
    def identity(self) -> tuple[int, int]:
        return windows_directory_identity(self._handle)

    def close(self) -> None:
        if self._handle < 0:
            return
        handles = [*self._ancestor_handles, self._handle]
        self._handle = -1
        self._ancestor_handles = ()
        close_windows_path_resources(
            handles, leaf_file_descriptor=-1, primary_exception=sys.exception()
        )

    def open_directory(self, name: str) -> WindowsAnchoredDirectory:
        return WindowsAnchoredDirectory(
            self._open_entry(name, directory=True, writable=True),
            deadline=self._deadline,
            cancellation=self._cancellation,
        )

    def create_directory(self, name: str) -> WindowsAnchoredDirectory:
        return WindowsAnchoredDirectory(
            self._open_entry(name, directory=True, create=True),
            deadline=self._deadline,
            cancellation=self._cancellation,
        )

    def write_file(self, name: str, content: bytes, *, posix_executable: bool = False) -> None:
        _ = posix_executable
        handle = self._open_entry(name, directory=False, create=True)
        descriptor = convert_windows_handle_to_file_descriptor(handle, writable=True)
        try:
            write_all_descriptor_bytes(
                descriptor, content, error_message="Workspace file write made no progress."
            )
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def open_file(
        self, name: str, *, create: bool = False, delete: bool = False, writable: bool = False
    ) -> int:
        handle = self._open_entry(
            name, directory=False, create=create, delete=delete, writable=create or writable
        )
        return convert_windows_handle_to_file_descriptor(handle, writable=create or writable)

    def publish_file_descriptor(self, descriptor: int, destination: str) -> None:
        publish_windows_entry_handle(
            windows_handle_from_descriptor(descriptor), self._handle, destination
        )

    def read_file(
        self, name: str, maximum_bytes: int, *, posix_executable: bool | None = None
    ) -> bytes:
        _ = posix_executable
        handle = self._open_entry(name, directory=False)
        descriptor = convert_windows_handle_to_file_descriptor(handle)
        try:
            return read_exclusive_regular_descriptor(descriptor, maximum_bytes)
        finally:
            os.close(descriptor)

    def names(self) -> tuple[str, ...]:
        return list_windows_directory(self._handle)

    def remove_file(self, name: str) -> None:
        self._remove_entry(name, directory=False)

    def remove_directory(
        self, name: str, *, expected_identity: tuple[int, int] | None = None
    ) -> None:
        self._remove_entry(name, directory=True, expected_identity=expected_identity)

    def _remove_entry(
        self, name: str, *, directory: bool, expected_identity: tuple[int, int] | None = None
    ) -> None:
        expected_parent = self.identity
        expected_entry = expected_identity
        opened = False

        def open_owned() -> int:
            nonlocal expected_entry, opened
            handle = self._open_entry(name, directory=directory, delete=True)
            accepted = False
            try:
                identity = windows_directory_identity(handle)
                if expected_entry is not None and identity != expected_entry:
                    raise StateError("Anchored cleanup entry identity changed.")
                expected_entry = identity
                opened = True
                accepted = True
                return handle
            finally:
                if not accepted:
                    close_windows_path_resources(
                        [handle], leaf_file_descriptor=-1, primary_exception=sys.exception()
                    )

        def remove_or_reconcile() -> None:
            try:
                remove_windows_entry(self._handle, name, directory=directory, opener=open_owned)
            except FileNotFoundError:
                if not opened:
                    raise

        def require_parent_identity() -> None:
            if self.identity != expected_parent:
                raise StateError("Anchored cleanup parent changed during contention.")

        retry_windows_sharing_conflicts(
            remove_or_reconcile,
            path=None,
            deadline=lambda: self._deadline,
            cancellation=self._cancellation,
            validate_identity=require_parent_identity,
        )

    def publish_directory(self, source: str, destination: str) -> None:
        original = self.open_directory(source)
        try:
            expected_source = original.identity
        finally:
            original.close()
        parent_identity = self.identity

        def require_parent_identity() -> None:
            if self.identity != parent_identity:
                raise StateError("Anchored publication parent identity changed during contention.")

        def publish_or_reconcile() -> None:
            try:
                staging = self.open_directory(source)
            except FileNotFoundError as exception:
                published = self.open_directory(destination)
                try:
                    if published.identity != expected_source:
                        raise StateError(
                            "Anchored publication destination identity changed."
                        ) from exception
                    return
                finally:
                    published.close()
            try:
                if staging.identity != expected_source:
                    raise StateError("Anchored publication source identity changed.")
            finally:
                staging.close()
            rename_file_without_replacement(source, destination, directory_handle=self._handle)

        retry_windows_sharing_conflicts(
            publish_or_reconcile,
            path=None,
            deadline=lambda: self._deadline,
            cancellation=self._cancellation,
            validate_identity=require_parent_identity,
        )

    def flush(self) -> None:
        expected = self.identity

        def require_identity() -> None:
            if self.identity != expected:
                raise StateError("Anchored directory identity changed during flush contention.")

        retry_windows_sharing_conflicts(
            partial(flush_windows_directory, self._handle),
            path=None,
            deadline=lambda: self._deadline,
            cancellation=self._cancellation,
            validate_identity=require_identity,
        )

    def _open_entry(
        self,
        name: str,
        *,
        directory: bool,
        create: bool = False,
        writable: bool = False,
        delete: bool = False,
    ) -> int:
        expected = self.identity

        def require_identity() -> None:
            if self.identity != expected:
                raise StateError("Anchored parent identity changed during open contention.")

        return retry_windows_sharing_conflicts(
            partial(
                open_relative_windows_entry,
                self._handle,
                name,
                directory=directory,
                create=create,
                writable=writable,
                delete=delete,
            ),
            path=None,
            deadline=lambda: self._deadline,
            cancellation=self._cancellation,
            validate_identity=require_identity,
        )


def open_windows_anchored_directory(
    path: str,
    *,
    deadline: MonotonicDeadline | None = None,
    cancellation: CancellationTokenProtocol | None = None,
) -> WindowsAnchoredDirectory:
    absolute = os.path.abspath(path)
    drive, remainder = os.path.splitdrive(absolute)
    if not drive:
        raise StateError("Anchored publication requires an absolute Windows workspace.")
    segments = tuple(segment for segment in remainder.split(os.sep) if segment)
    library = load_kernel32()
    create = library.CreateFileW
    create.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    )
    create.restype = ctypes.c_void_p
    volume_handle = create(
        normalize_filesystem_path(drive + os.sep),
        0x00100081 | (0x00000116 if not segments else 0),
        3,
        None,
        3,
        0x02200000,
        None,
    )
    if volume_handle is None or volume_handle == ctypes.c_void_p(-1).value:
        error_number = last_windows_error()
        raise OSError(
            error_number, "Windows workspace volume could not be anchored.", None, error_number
        )
    handles = [int(volume_handle)]
    try:
        for index, segment in enumerate(segments):
            handles.append(
                open_relative_windows_entry(
                    handles[-1], segment, directory=True, writable=index == len(segments) - 1
                )
            )
        result = WindowsAnchoredDirectory(
            handles[-1],
            ancestor_handles=tuple(handles[:-1]),
            deadline=deadline,
            cancellation=cancellation,
        )
        handles = []
        return result
    finally:
        close_windows_path_resources(
            handles, leaf_file_descriptor=-1, primary_exception=sys.exception()
        )
