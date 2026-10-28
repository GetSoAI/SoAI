"""SoAI - Identity-stamped process descendant enumeration [backend/core/runtime/process_descendants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

from core.filesystem.open_files import open_binary, open_text
from core.platform.os import is_linux, is_windows
from core.runtime.process_identity_signals import read_process_create_time_ms

if TYPE_CHECKING:
    type ProcessDescendantObservation = list[tuple[psutil.Process, int]] | psutil.Error | OSError

__all__ = (
    "PROCESS_OBSERVATION_FAILURES",
    "list_process_descendants",
    "list_process_descendants_batch",
)

PROCESS_OBSERVATION_FAILURES: tuple[type[psutil.Error], type[OSError]] = (psutil.Error, OSError)
LINUX_PROCESS_STAT_MAX_BYTES = 8192


@dataclass(frozen=True, slots=True)
class LinuxProcessStat:
    parent_pid: int
    start_token: int


def list_process_descendants(process: psutil.Process) -> list[tuple[psutil.Process, int]]:
    if is_linux() and _linux_proc_children_supported():
        linux_descendants = _list_linux_process_descendants(process)
        if linux_descendants is not None:
            return linux_descendants
    return _list_psutil_process_descendants(process)


def list_process_descendants_batch(
    processes: Sequence[psutil.Process],
) -> dict[int, ProcessDescendantObservation]:
    observations: dict[int, ProcessDescendantObservation] = {}
    census_roots: list[psutil.Process] = []
    linux_children = is_linux() and _linux_proc_children_supported()
    for process in processes:
        try:
            if linux_children:
                linux_descendants = _list_linux_process_descendants(process)
                if linux_descendants is not None:
                    observations[process.pid] = linux_descendants
                    continue
            if is_windows():
                observations[process.pid] = _list_psutil_process_descendants(process)
                continue
        except PROCESS_OBSERVATION_FAILURES as exception:
            observations[process.pid] = exception
            continue
        census_roots.append(process)
    if not census_roots:
        return observations
    if is_linux():
        observations.update(_observe_linux_process_census(census_roots))
        return observations
    try:
        children_by_parent = _read_posix_process_census()
    except PROCESS_OBSERVATION_FAILURES as exception:
        observations.update((process.pid, exception) for process in census_roots)
        return observations
    for process in census_roots:
        try:
            observations[process.pid] = _list_census_descendants(process, children_by_parent)
        except PROCESS_OBSERVATION_FAILURES as exception:
            observations[process.pid] = exception
    return observations


def _observe_linux_process_census(
    roots: Sequence[psutil.Process],
) -> dict[int, ProcessDescendantObservation]:
    observations: dict[int, ProcessDescendantObservation] = {}
    process_stats: dict[int, LinuxProcessStat] = {}
    children_by_parent: dict[int, list[int]] = {}
    try:
        for candidate in os.listdir("/proc"):
            if not candidate.isdecimal():
                continue
            candidate_pid = int(candidate)
            process_stat = _read_linux_process_stat(candidate_pid)
            if process_stat is None:
                continue
            process_stats[candidate_pid] = process_stat
            if process_stat.parent_pid not in children_by_parent:
                children_by_parent[process_stat.parent_pid] = []
            children_by_parent[process_stat.parent_pid].append(candidate_pid)
    except PROCESS_OBSERVATION_FAILURES as exception:
        return {process.pid: exception for process in roots}
    for process in roots:
        try:
            observations[process.pid] = _list_linux_census_descendants(
                process, process_stats, children_by_parent
            )
        except PROCESS_OBSERVATION_FAILURES as exception:
            observations[process.pid] = exception
    return observations


def _read_linux_process_stat(pid: int) -> LinuxProcessStat | None:
    try:
        with open_binary(f"/proc/{pid}/stat", mode="rb", buffering=0) as stat_file:
            raw_stat = stat_file.read(LINUX_PROCESS_STAT_MAX_BYTES + 1).decode(
                "ascii", errors="surrogateescape"
            )
    except (FileNotFoundError, ProcessLookupError):
        return None
    command_end = raw_stat.rfind(")")
    raw_pid, separator, _command = raw_stat[:command_end].partition(" (")
    fields = raw_stat[command_end + 1 :].split()
    structure_valid = bool(separator) and raw_pid == str(pid) and len(fields) >= 20
    if len(raw_stat) > LINUX_PROCESS_STAT_MAX_BYTES or command_end < 0 or not structure_valid:
        raise OSError(f"Process {pid} returned an invalid bounded stat observation.")
    if (
        len(fields[0]) != 1
        or not fields[1].isdecimal()
        or not fields[19].isdecimal()
        or len(fields[1]) > 20
        or len(fields[19]) > 20
    ):
        raise OSError(f"Process {pid} returned an invalid bounded stat observation.")
    return LinuxProcessStat(int(fields[1]), int(fields[19]))


def _list_linux_census_descendants(
    process: psutil.Process,
    process_stats: dict[int, LinuxProcessStat],
    children_by_parent: dict[int, list[int]],
) -> list[tuple[psutil.Process, int]]:
    if not process.is_running() or process.pid not in process_stats:
        raise psutil.NoSuchProcess(process.pid)
    root_create_time_ms = read_process_create_time_ms(process)
    descendants: list[tuple[psutil.Process, int]] = []
    visited_pids = {process.pid}
    pending = [(process, root_create_time_ms)]
    while pending:
        parent, parent_create_time_ms = pending.pop()
        observed_parent = _read_linux_process_stat(parent.pid)
        if (
            not parent.is_running()
            or observed_parent is None
            or observed_parent.start_token != process_stats[parent.pid].start_token
            or (
                parent.pid != process.pid
                and observed_parent.parent_pid != process_stats[parent.pid].parent_pid
            )
        ):
            if parent.pid == process.pid:
                raise psutil.NoSuchProcess(process.pid)
            continue
        for child_pid in children_by_parent.get(parent.pid, ()):
            if child_pid in visited_pids:
                continue
            visited_pids.add(child_pid)
            try:
                child = psutil.Process(child_pid)
                child_create_time_ms = read_process_create_time_ms(child)
                observed_child = _read_linux_process_stat(child_pid)
                if (
                    observed_child != process_stats[child_pid]
                    or not child.is_running()
                    or child_create_time_ms < parent_create_time_ms
                ):
                    continue
            except psutil.NoSuchProcess:
                continue
            descendants.append((child, child_create_time_ms))
            pending.append((child, child_create_time_ms))
    return descendants


def _read_posix_process_census() -> dict[int, list[int]]:
    children_by_parent: dict[int, list[int]] = {}
    for candidate in psutil.process_iter(["ppid"]):
        parent_pid = candidate.info.get("ppid")
        if not isinstance(parent_pid, int):
            continue
        if parent_pid not in children_by_parent:
            children_by_parent[parent_pid] = []
        children_by_parent[parent_pid].append(candidate.pid)
    return children_by_parent


def _list_census_descendants(
    process: psutil.Process,
    children_by_parent: dict[int, list[int]],
) -> list[tuple[psutil.Process, int]]:
    if not process.is_running():
        raise psutil.NoSuchProcess(process.pid)
    root_create_time_ms = read_process_create_time_ms(process)
    descendants: list[tuple[psutil.Process, int]] = []
    visited_pids = {process.pid}
    pending_pids = [process.pid]
    while pending_pids:
        for child_pid in children_by_parent.get(pending_pids.pop(), ()):
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
            descendants.append((child, child_create_time_ms))
            pending_pids.append(child_pid)
    return descendants


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
