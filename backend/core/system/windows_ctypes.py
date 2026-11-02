"""SoAI - Windows ctypes helpers [backend/core/system/windows_ctypes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os
import sys
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.platform.os import is_windows

__all__ = (
    "last_windows_error",
    "load_kernel32",
    "load_windows_library",
    "load_windows_system_library",
    "resolve_windll",
)


def load_kernel32() -> ctypes.CDLL:
    if not is_windows():
        raise StateError("Windows kernel32 access requires Windows.")
    if sys.platform != "win32":
        raise StateError("Windows platform detection is inconsistent.")
    return ctypes.WinDLL("kernel32", use_last_error=True)


def load_windows_library(name: str, *, use_last_error: bool = False) -> ctypes.CDLL:
    if not is_windows():
        raise StateError("Windows library loading requires Windows.")
    if sys.platform != "win32":
        raise StateError("Windows platform detection is inconsistent.")
    return ctypes.WinDLL(name, use_last_error=use_last_error)


def load_windows_system_library(name: str) -> ctypes.CDLL:
    if (
        not name
        or "/" in name
        or "\\" in name
        or ":" in name
        or not name.casefold().endswith(".dll")
    ):
        raise StateError("Windows system library requires a DLL filename.")
    kernel = load_kernel32()
    kernel.GetSystemDirectoryW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetSystemDirectoryW.restype = ctypes.c_uint32
    directory = ctypes.create_unicode_buffer(32768)
    length = kernel.GetSystemDirectoryW(directory, len(directory))
    if length == 0 or length >= len(directory) or not os.path.isabs(directory.value):
        raise StateError("Windows trusted native library directory is unavailable.")
    return ctypes.CDLL(os.path.join(directory.value, name), winmode=0x00000900)


def last_windows_error() -> int:
    if not is_windows():
        raise StateError("Windows error inspection requires Windows.")
    if sys.platform != "win32":
        raise StateError("Windows platform detection is inconsistent.")
    return ctypes.get_last_error()


def resolve_windll() -> ctypes.LibraryLoader[ctypes.CDLL] | None:
    if TYPE_CHECKING:
        windll = None
    else:
        try:
            windll = ctypes.windll
        except AttributeError:
            windll = None
    return windll
