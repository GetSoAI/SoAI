"""SoAI - Disk reservation process identity helpers [backend/core/hardware/disk_reservation_processes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.filesystem.open_files import open_text

__all__ = (
    "is_process_reservation_stale",
    "read_process_start_token",
)


def read_process_start_token(pid: int) -> str:
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
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    except OSError:
        return False
    current_token = read_process_start_token(pid)
    return bool(current_token and process_start_token and current_token != process_start_token)
