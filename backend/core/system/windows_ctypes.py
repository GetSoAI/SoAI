"""SoAI - Windows ctypes helpers [backend/core/system/windows_ctypes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import sys
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.platform.os import is_windows

__all__ = (
    "last_windows_error",
    "load_kernel32",
    "load_windows_library",
    "resolve_windll",
)


def load_kernel32() -> ctypes.CDLL:
    if not is_windows():
        raise StateError("Windows kernel32 access requires Windows.")
    if sys.platform != "win32":
        raise StateError("Windows platform detection is inconsistent.")
    return ctypes.WinDLL("kernel32", use_last_error=True)


def load_windows_library(name: str) -> ctypes.CDLL:
    if not is_windows():
        raise StateError("Windows library loading requires Windows.")
    if sys.platform != "win32":
        raise StateError("Windows platform detection is inconsistent.")
    return ctypes.WinDLL(name)


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
