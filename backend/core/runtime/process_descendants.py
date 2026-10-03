"""SoAI - Identity-stamped process descendant enumeration [backend/core/runtime/process_descendants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import threading

import psutil

from core.filesystem.open_files import open_text
from core.platform.os import is_linux
from core.runtime.process_identity_signals import read_process_create_time_ms

__all__ = ("list_process_descendants",)


def list_process_descendants(process: psutil.Process) -> list[tuple[psutil.Process, int]]:
    if is_linux() and _linux_proc_children_supported():
        linux_descendants = _list_linux_process_descendants(process)
        if linux_descendants is not None:
            return linux_descendants
    return _list_psutil_process_descendants(process)


def _list_psutil_process_descendants(
    process: psutil.Process,
) -> list[tuple[psutil.Process, int]]:
    descendants: list[tuple[psutil.Process, int]] = []
    for child in process.children(recursive=True):
        try:
            descendants.append((child, read_process_create_time_ms(child)))
        except psutil.NoSuchProcess:
            continue
    return descendants


def _linux_proc_children_supported() -> bool:
    return os.path.exists(f"/proc/self/task/{threading.get_native_id()}/children")


def _list_linux_process_descendants(
    process: psutil.Process,
) -> list[tuple[psutil.Process, int]] | None:
    if not process.is_running():
        raise psutil.NoSuchProcess(process.pid)
    root_create_time_ms = read_process_create_time_ms(process)
    root_child_pids = _read_linux_child_pids(process.pid)
    if root_child_pids is None:
        return None
    descendants: list[tuple[psutil.Process, int]] = []
    visited_pids = {process.pid}
    pending_pids = list(root_child_pids)
    while pending_pids:
        child_pid = pending_pids.pop()
        if child_pid in visited_pids:
            continue
        visited_pids.add(child_pid)
        try:
            child = psutil.Process(child_pid)
            child_create_time_ms = read_process_create_time_ms(child)
        except psutil.NoSuchProcess:
            continue
        if child_create_time_ms < root_create_time_ms:
            continue
        grandchild_pids = _read_linux_child_pids(child_pid)
        if grandchild_pids is None:
            return None
        descendants.append((child, child_create_time_ms))
        pending_pids.extend(grandchild_pids)
    return descendants


def _read_linux_child_pids(pid: int) -> list[int] | None:
    task_directory = f"/proc/{pid}/task"
    try:
        thread_ids = os.listdir(task_directory)
    except (FileNotFoundError, ProcessLookupError):
        return []
    except OSError:
        return None
    child_pids: list[int] = []
    for thread_id in thread_ids:
        try:
            with open_text(
                f"{task_directory}/{thread_id}/children",
                mode="r",
                encoding="ascii",
                errors="strict",
            ) as children_file:
                raw_child_pids = children_file.read()
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (OSError, UnicodeDecodeError):
            return None
        for raw_child_pid in raw_child_pids.split():
            if not raw_child_pid.isdigit():
                return None
            child_pids.append(int(raw_child_pid))
    return child_pids
