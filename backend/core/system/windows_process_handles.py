"""SoAI - Retained Windows process identity handles [backend/core/system/windows_process_handles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from ctypes import wintypes

from core.system.windows_ctypes import last_windows_error, load_kernel32
from core.validation.strict_numbers import require_positive_int_strict

__all__ = ("retain_windows_process_handle",)

_SYNCHRONIZE = 0x00100000


def retain_windows_process_handle(process_id: int) -> int:
    require_positive_int_strict(process_id, error_message="Process identity must be positive.")
    kernel32 = load_kernel32()
    open_process = kernel32.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    handle = open_process(_SYNCHRONIZE, False, process_id)
    if not handle:
        error_number = last_windows_error()
        raise OSError(error_number, os.strerror(error_number))
    return int(handle)
