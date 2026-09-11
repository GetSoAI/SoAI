"""SoAI - Preserve Windows entry access controls during installation copies [backend/core/filesystem/windows_access_control.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from core.errors.exceptions import StateError
from core.filesystem.path_coercion import normalize_filesystem_path
from core.system.windows_ctypes import last_windows_error, load_kernel32

__all__ = ("copy_windows_discretionary_acl",)

_FILE_OBJECT = 1
_DACL_SECURITY_INFORMATION = 4


def copy_windows_discretionary_acl(source: str, destination: str) -> None:
    if sys.platform != "win32":
        raise StateError("Windows access-control copying requires Windows.")
    source = normalize_filesystem_path(source)
    destination = normalize_filesystem_path(destination)
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    get_security = security.GetNamedSecurityInfoW
    get_security.argtypes = (
        wintypes.LPCWSTR,
        ctypes.c_int,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    )
    get_security.restype = wintypes.DWORD
    set_security = security.SetFileSecurityW
    set_security.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p)
    set_security.restype = wintypes.BOOL
    kernel32 = load_kernel32()
    free_descriptor = kernel32.LocalFree
    free_descriptor.argtypes = (ctypes.c_void_p,)
    free_descriptor.restype = ctypes.c_void_p
    descriptor = ctypes.c_void_p()
    error_number = get_security(
        source,
        _FILE_OBJECT,
        _DACL_SECURITY_INFORMATION,
        None,
        None,
        None,
        None,
        ctypes.byref(descriptor),
    )
    if error_number:
        raise OSError(error_number, "Could not read Windows entry access controls.", source)
    try:
        if not set_security(destination, _DACL_SECURITY_INFORMATION, descriptor):
            error_number = last_windows_error()
            raise OSError(
                error_number, "Could not preserve Windows entry access controls.", destination
            )
    finally:
        if free_descriptor(descriptor):
            release_error = OSError(
                last_windows_error(), "Could not release Windows security descriptor."
            )
            primary_exception = sys.exception()
            if primary_exception is not None:
                primary_exception.add_note(str(release_error))
            else:
                raise release_error
