"""SoAI - Disk reservation process identity helpers [backend/core/hardware/disk_reservation_processes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import psutil

from core.errors.exceptions import StateError
from core.filesystem.open_files import open_text
from core.platform.os import is_linux, is_windows
from core.runtime.process_identity_signals import read_process_create_time_ms
from core.system.pid_liveness import pid_is_running

__all__ = (
    "is_process_reservation_stale",
    "read_process_start_token",
)

_WINDOWS_START_TOKEN_PREFIX = "windows-create-time-ms:"


def read_process_start_token(pid: int) -> str:
    if pid <= 0:
        return ""
    if is_windows():
        try:
            created_at_ms = read_process_create_time_ms(psutil.Process(pid))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return ""
        except psutil.Error as exception:
            raise StateError(
                "Disk reservation process identity could not be inspected."
            ) from exception
        return f"{_WINDOWS_START_TOKEN_PREFIX}{created_at_ms}"
    if not is_linux():
        return ""
    proc_stat_path = f"/proc/{pid}/stat"
    try:
        with open_text(proc_stat_path, mode="r", encoding="utf-8", errors="strict") as handle:
            raw_stat = handle.read()
    except OSError:
        return ""
    command_end_index = raw_stat.rfind(")")
    if command_end_index < 0:
        return ""
    fields = raw_stat[command_end_index + 2 :].split()
    if len(fields) < 20:
        return ""
    return fields[19]


def is_process_reservation_stale(pid: int, process_start_token: str) -> bool:
    if pid <= 0:
        return True
    try:
        if not pid_is_running(pid, raise_on_access_denied=True):
            return True
    except OSError:
        return False
    if is_windows() and (
        not process_start_token.startswith(_WINDOWS_START_TOKEN_PREFIX)
        or not process_start_token.removeprefix(_WINDOWS_START_TOKEN_PREFIX).isdecimal()
    ):
        return False
    current_token = read_process_start_token(pid)
    return bool(current_token and process_start_token and current_token != process_start_token)
