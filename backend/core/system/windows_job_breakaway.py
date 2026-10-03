"""SoAI - Windows job breakaway resolution for detached handoff processes [backend/core/system/windows_job_breakaway.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from ctypes import wintypes

from core.errors.exceptions import StateError
from core.platform.os import is_windows
from core.system.subprocess_platform import (
    WINDOWS_CREATE_BREAKAWAY_FROM_JOB,
    windows_isolated_process_creationflags,
)
from core.system.windows_ctypes import last_windows_error, load_kernel32

__all__ = ("windows_handoff_process_creationflags",)

_JOB_OBJECT_BASIC_LIMIT_INFORMATION_CLASS = 2
_JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
_JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x00001000
_BASIC_LIMIT_FIXED_BYTES = 32
_BASIC_LIMIT_FLAGS_DWORD_INDEX = 4


def windows_handoff_process_creationflags() -> int:
    if not is_windows():
        return 0
    return windows_isolated_process_creationflags() | _job_breakaway_creationflags()


def _job_breakaway_creationflags() -> int:
    kernel32 = load_kernel32()
    is_process_in_job = kernel32.IsProcessInJob
    is_process_in_job.argtypes = (wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL))
    is_process_in_job.restype = wintypes.BOOL
    get_current_process = kernel32.GetCurrentProcess
    get_current_process.argtypes = ()
    get_current_process.restype = wintypes.HANDLE
    in_job = wintypes.BOOL()
    if not is_process_in_job(get_current_process(), None, ctypes.byref(in_job)):
        raise StateError(
            "Windows job membership could not be inspected.",
            details={"windows_error": last_windows_error()},
        )
    if not in_job.value:
        return 0
    query_information = kernel32.QueryInformationJobObject
    query_information.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    query_information.restype = wintypes.BOOL
    pointer_size = ctypes.sizeof(ctypes.c_void_p)
    information = (ctypes.c_uint32 * ((_BASIC_LIMIT_FIXED_BYTES + 4 * pointer_size) // 4))()
    if not query_information(
        None,
        _JOB_OBJECT_BASIC_LIMIT_INFORMATION_CLASS,
        ctypes.byref(information),
        ctypes.sizeof(information),
        None,
    ):
        raise StateError(
            "Windows job limits could not be inspected.",
            details={"windows_error": last_windows_error()},
        )
    limit_flags = int(information[_BASIC_LIMIT_FLAGS_DWORD_INDEX])
    if limit_flags & _JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK:
        return 0
    if limit_flags & _JOB_OBJECT_LIMIT_BREAKAWAY_OK:
        return WINDOWS_CREATE_BREAKAWAY_FROM_JOB
    return 0
