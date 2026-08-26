"""SoAI - PID liveness helpers [backend/core/system/pid_liveness.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os

from core.platform.os import is_windows
from core.system.windows_ctypes import resolve_windll

__all__ = ("pid_is_running",)


def pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if is_windows():
        return _windows_pid_is_running(pid)
    is_running = False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        is_running = False
    except PermissionError:
        is_running = True
    else:
        is_running = True
    return is_running


def _windows_pid_is_running(pid: int) -> bool:
    windll = resolve_windll()
    if windll is None:
        return False
    process_query_limited_information = 0x1000
    handle = windll.kernel32.OpenProcess(
        process_query_limited_information,
        False,
        int(pid),
    )
    if not handle:
        return False
    try:
        active_code = 259
        exit_code = ctypes.c_ulong()
        success = windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        return bool(success) and int(exit_code.value) == active_code
    finally:
        windll.kernel32.CloseHandle(handle)
