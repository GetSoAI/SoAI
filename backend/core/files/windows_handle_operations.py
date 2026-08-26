"""SoAI - Low-level Windows file handle operations [backend/core/files/windows_handle_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

from core.files.managed_storage_errors import FileStorageSecurityError
from core.platform.os import is_windows
from core.system.windows_ctypes import last_windows_error, load_kernel32

__all__ = (
    "close_windows_handle",
    "convert_windows_handle_to_file_descriptor",
    "mark_windows_file_descriptor_for_deletion",
)

_FILE_DISPOSITION_INFO_CLASS = 4
_OPEN_BINARY = 0x8000


if is_windows() and sys.platform == "win32":
    import msvcrt

    def _descriptor_from_windows_handle(handle: int) -> int:
        return msvcrt.open_osfhandle(handle, os.O_RDONLY | _OPEN_BINARY)

    def _windows_handle_from_descriptor(descriptor: int) -> int:
        return msvcrt.get_osfhandle(descriptor)

else:

    def _descriptor_from_windows_handle(handle: int) -> int:
        _ = handle
        raise FileStorageSecurityError("Windows file handle conversion requires Windows.")

    def _windows_handle_from_descriptor(descriptor: int) -> int:
        _ = descriptor
        raise FileStorageSecurityError(
            "Windows file descriptor inspection requires Windows.",
        )


def close_windows_handle(handle: int) -> None:
    kernel32 = load_kernel32()
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    if not close_handle(wintypes.HANDLE(handle)):
        error_number = last_windows_error()
        raise OSError(error_number, os.strerror(error_number))


def convert_windows_handle_to_file_descriptor(handle: int) -> int:
    converted = False
    try:
        descriptor = int(_descriptor_from_windows_handle(handle))
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
        handle = int(_windows_handle_from_descriptor(descriptor))
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
