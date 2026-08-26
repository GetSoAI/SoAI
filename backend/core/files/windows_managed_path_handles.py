"""SoAI - Stable Windows handles for managed storage traversal [backend/core/files/windows_managed_path_handles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os
import stat
import sys
from contextlib import AbstractContextManager
from ctypes import wintypes
from dataclasses import dataclass
from types import TracebackType
from typing import override

from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.managed_storage_traversal import normalize_storage_relative_path
from core.files.path_policy import is_same_path
from core.files.windows_handle_operations import (
    close_windows_handle,
    convert_windows_handle_to_file_descriptor,
)
from core.platform.os import is_windows
from core.system.windows_ctypes import last_windows_error, load_kernel32

__all__ = (
    "WindowsManagedPathHandles",
    "open_windows_managed_path_handles",
)

_FILE_ATTRIBUTE_DIRECTORY = 0x10
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_READ_ATTRIBUTES = 0x80
_GENERIC_READ = 0x80000000
_DELETE = 0x00010000
_OPEN_EXISTING = 3
_SHARE_READ = 1
_SHARE_DELETE = 4
_WINDOWS_INVALID_HANDLE_VALUE = -1


@dataclass(frozen=True, slots=True)
class _HandleFileInformation:
    file_attributes: int


class WindowsManagedPathHandles(AbstractContextManager["WindowsManagedPathHandles"]):
    __slots__ = ("_handles", "_leaf_file_descriptor", "path", "stat_result")

    def __init__(
        self,
        handles: list[int],
        *,
        leaf_file_descriptor: int,
        path: str,
        stat_result: os.stat_result,
    ) -> None:
        self._handles = handles
        self._leaf_file_descriptor = leaf_file_descriptor
        self.path = path
        self.stat_result = stat_result

    def detach_leaf_file_descriptor(self) -> int:
        if self._leaf_file_descriptor < 0:
            raise FileStorageSecurityError("Managed Windows path handle is already closed.")
        descriptor = self._leaf_file_descriptor
        _close_windows_path_resources(
            self._handles,
            leaf_file_descriptor=-1,
            primary_exception=None,
        )
        self._leaf_file_descriptor = -1
        return descriptor

    def close(self, primary_exception: BaseException | None = None) -> None:
        leaf_file_descriptor = self._leaf_file_descriptor
        self._leaf_file_descriptor = -1
        _close_windows_path_resources(
            self._handles,
            leaf_file_descriptor=leaf_file_descriptor,
            primary_exception=primary_exception,
        )

    @override
    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = exception_type, traceback
        self.close(primary_exception=exception)


def open_windows_managed_path_handles(
    storage_root: str,
    entry_path: str,
    *,
    require_directory: bool | None,
    read_leaf: bool = False,
    allow_leaf_delete: bool = False,
) -> WindowsManagedPathHandles:
    if not is_windows():
        raise FileStorageSecurityError("Windows managed path handles require Windows.")
    if allow_leaf_delete and not read_leaf:
        raise FileStorageSecurityError("Windows leaf deletion requires a readable file handle.")
    root_path = os.path.abspath(storage_root)
    if is_same_path(root_path, entry_path):
        parts: list[str] = []
    else:
        parts = normalize_storage_relative_path(root_path, entry_path)
    paths = [root_path]
    current_path = root_path
    for part in parts:
        current_path = os.path.join(current_path, part)
        paths.append(current_path)
    handles: list[int] = []
    leaf_file_descriptor = -1
    completed = False
    try:
        for index, path in enumerate(paths):
            leaf = index == len(paths) - 1
            handle = _open_path_handle(
                path,
                read_content=leaf and read_leaf,
                allow_delete=leaf and allow_leaf_delete,
            )
            handles.append(handle)
            information = _read_handle_information(handle, path)
            attributes = int(information.file_attributes)
            if attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                raise FileStorageSecurityError(
                    f"Managed path contains a Windows reparse point: '{path}'.",
                )
            is_directory = bool(attributes & _FILE_ATTRIBUTE_DIRECTORY)
            if not leaf and not is_directory:
                raise FileStorageSecurityError(
                    f"Managed path ancestor is not a directory: '{path}'.",
                )
            if leaf and require_directory is True and not is_directory:
                raise FileStorageSecurityError("Managed path is not a directory.")
            if leaf and require_directory is False and is_directory:
                raise FileStorageSecurityError("Managed path is not a regular file.")
            if leaf and read_leaf:
                handles.pop()
                leaf_file_descriptor = convert_windows_handle_to_file_descriptor(handle)
        stat_result = (
            os.fstat(leaf_file_descriptor)
            if leaf_file_descriptor >= 0
            else os.stat(current_path, follow_symlinks=False)
        )
        if require_directory is False and not stat.S_ISREG(stat_result.st_mode):
            raise FileStorageSecurityError("Managed path is not a regular file.")
        opened_path = WindowsManagedPathHandles(
            handles,
            leaf_file_descriptor=leaf_file_descriptor,
            path=current_path,
            stat_result=stat_result,
        )
        completed = True
        return opened_path
    finally:
        if not completed:
            _close_windows_path_resources(
                handles,
                leaf_file_descriptor=leaf_file_descriptor,
                primary_exception=sys.exception(),
            )


def _open_path_handle(path: str, *, read_content: bool, allow_delete: bool) -> int:
    _require_64_bit_windows()
    kernel32 = load_kernel32()
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    desired_access = _GENERIC_READ if read_content else _FILE_READ_ATTRIBUTES
    share_mode = _SHARE_READ
    if allow_delete:
        desired_access |= _DELETE
        share_mode |= _SHARE_DELETE
    handle = create_file(
        _to_extended_path(path),
        desired_access,
        share_mode,
        None,
        _OPEN_EXISTING,
        _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if handle is None or handle == wintypes.HANDLE(_WINDOWS_INVALID_HANDLE_VALUE).value:
        error_number = last_windows_error()
        error_type = FileNotFoundError if error_number in {2, 3} else OSError
        cause = error_type(error_number, os.strerror(error_number), path)
        raise FileStorageSecurityError(
            f"Managed Windows path could not be opened: '{path}'."
        ) from cause
    return int(handle)


def _read_handle_information(handle: int, path: str) -> _HandleFileInformation:
    kernel32 = load_kernel32()
    get_information = kernel32.GetFileInformationByHandle
    get_information.argtypes = (
        wintypes.HANDLE,
        wintypes.LPVOID,
    )
    get_information.restype = wintypes.BOOL
    information = (wintypes.DWORD * 13)()
    if not get_information(wintypes.HANDLE(handle), ctypes.byref(information)):
        error_number = last_windows_error()
        cause = OSError(error_number, os.strerror(error_number), path)
        raise FileStorageSecurityError(
            f"Managed Windows path handle could not be inspected: '{path}'.",
        ) from cause
    return _HandleFileInformation(file_attributes=int(information[0]))


def _require_64_bit_windows() -> None:
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise FileStorageSecurityError(
            "Secure managed Windows path handles require a 64-bit runtime.",
        )


def _close_windows_path_resources(
    handles: list[int],
    *,
    leaf_file_descriptor: int,
    primary_exception: BaseException | None,
) -> None:
    first_close_exception: OSError | None = None
    if leaf_file_descriptor >= 0:
        try:
            os.close(leaf_file_descriptor)
        except OSError as close_exception:
            first_close_exception = close_exception
    while handles:
        try:
            close_windows_handle(handles.pop())
        except OSError as close_exception:
            if first_close_exception is None:
                first_close_exception = close_exception
    if first_close_exception is None:
        return
    if primary_exception is not None:
        primary_exception.add_note(
            f"Failed to close managed Windows path handle: {first_close_exception}",
        )
        return
    raise FileStorageSecurityError(
        "Failed to close managed Windows path handle.",
    ) from first_close_exception


def _to_extended_path(path: str) -> str:
    absolute_path = os.path.abspath(path)
    if absolute_path.startswith("\\\\?\\"):
        return absolute_path
    if absolute_path.startswith("\\\\"):
        return f"\\\\?\\UNC\\{absolute_path[2:]}"
    return f"\\\\?\\{absolute_path}"
