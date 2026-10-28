"""SoAI - Low-level Windows file handle operations [backend/core/files/windows_handle_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from typing import TYPE_CHECKING

from core.files.commit_receipt import FilePublicationUncertainError
from core.files.managed_storage_errors import FileStorageSecurityError
from core.platform.os import is_windows
from core.system.windows_ctypes import last_windows_error, load_kernel32

__all__ = (
    "windows_handle_from_descriptor",
    "close_windows_handle",
    "close_windows_path_resources",
    "convert_windows_handle_to_file_descriptor",
    "mark_windows_file_descriptor_for_deletion",
    "query_windows_handle_attributes",
)

_FILE_DISPOSITION_INFO_CLASS = 4
_OPEN_BINARY = 0x8000


if TYPE_CHECKING or (is_windows() and sys.platform == "win32"):
    import msvcrt


if is_windows() and sys.platform == "win32":

    def _descriptor_from_windows_handle(handle: int, *, writable: bool = False) -> int:
        return msvcrt.open_osfhandle(
            handle, (os.O_RDWR if writable else os.O_RDONLY) | _OPEN_BINARY
        )

else:

    def _descriptor_from_windows_handle(handle: int, *, writable: bool = False) -> int:
        _ = handle, writable
        raise FileStorageSecurityError("Windows file handle conversion requires Windows.")


def windows_handle_from_descriptor(descriptor: int) -> int:
    if not is_windows() or sys.platform != "win32":
        raise FileStorageSecurityError(
            "Windows file descriptor inspection requires Windows.",
        )
    return msvcrt.get_osfhandle(descriptor)


def close_windows_handle(handle: int) -> None:
    kernel32 = load_kernel32()
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    if not close_handle(wintypes.HANDLE(handle)):
        error_number = last_windows_error()
        raise OSError(error_number, os.strerror(error_number))


def query_windows_handle_attributes(handle: int) -> int:
    information = ctypes.create_string_buffer(8)
    query = load_kernel32().GetFileInformationByHandleEx
    query.argtypes = (ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32)
    query.restype = ctypes.c_int32
    if not query(handle, 9, ctypes.byref(information), ctypes.sizeof(information)):
        error_number = last_windows_error()
        raise OSError(
            error_number,
            "Anchored Windows entry attributes could not be verified.",
            None,
            error_number,
        )
    return int.from_bytes(information.raw[:4], "little")


def convert_windows_handle_to_file_descriptor(handle: int, *, writable: bool = False) -> int:
    converted = False
    try:
        descriptor = int(_descriptor_from_windows_handle(handle, writable=writable))
        if descriptor < 0:
            raise OSError("Windows runtime rejected the managed file handle.")
        converted = True
        return descriptor
    finally:
        if not converted:
            primary_exception = sys.exception()
            try:
                close_windows_handle(handle)
            except OSError as close_exception:
                if primary_exception is not None:
                    primary_exception.add_note(
                        f"Failed to close Windows file handle: {close_exception}",
                    )
                else:
                    raise FileStorageSecurityError(
                        "Failed to close unconverted Windows file handle.",
                    ) from close_exception


def mark_windows_file_descriptor_for_deletion(descriptor: int) -> None:
    try:
        handle = int(windows_handle_from_descriptor(descriptor))
    except OSError as exception:
        raise FileStorageSecurityError(
            "Windows runtime rejected the temporary file descriptor.",
        ) from exception
    if handle == -1:
        raise FileStorageSecurityError("Windows runtime rejected the temporary file descriptor.")
    kernel32 = load_kernel32()
    set_information = kernel32.SetFileInformationByHandle
    set_information.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    set_information.restype = wintypes.BOOL
    disposition = ctypes.c_ubyte(1)
    if not set_information(
        wintypes.HANDLE(handle),
        _FILE_DISPOSITION_INFO_CLASS,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        error_number = last_windows_error()
        cause = OSError(error_number, os.strerror(error_number))
        raise FileStorageSecurityError(
            "Temporary Windows file could not be marked for deletion.",
        ) from cause


def close_windows_path_resources(
    handles: list[int],
    *,
    leaf_file_descriptor: int,
    primary_exception: BaseException | None,
) -> None:
    close_exceptions: list[OSError] = []
    if leaf_file_descriptor >= 0:
        try:
            os.close(leaf_file_descriptor)
        except OSError as close_exception:
            close_exceptions.append(close_exception)
    while handles:
        try:
            close_windows_handle(handles.pop())
        except OSError as close_exception:
            close_exceptions.append(close_exception)
    if not close_exceptions:
        return
    if primary_exception is not None:
        if isinstance(primary_exception, FilePublicationUncertainError):
            primary_exception.details = {
                **(primary_exception.details or {}),
                "cleanup_incomplete": True,
            }
        for secondary_exception in close_exceptions:
            primary_exception.add_note(
                f"Failed to close managed Windows path handle: {secondary_exception}",
            )
        return
    cleanup_exception = FileStorageSecurityError(
        "Failed to close managed Windows path handle.",
    )
    for secondary_exception in close_exceptions[1:]:
        cleanup_exception.add_note(
            f"Failed to close managed Windows path handle: {secondary_exception}",
        )
    raise cleanup_exception from close_exceptions[0]
