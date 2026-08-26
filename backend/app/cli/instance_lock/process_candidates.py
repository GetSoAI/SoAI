"""SoAI - Process discovery for instance locking [backend/app/cli/instance_lock/process_candidates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
from typing import TypeGuard

import psutil

from core.runtime.process_identity import (
    is_management_process_command,
    is_soai_instance_process,
    is_soai_owned_process_markers,
)

__all__ = (
    "discover_running_instance_pids",
    "find_pids_holding_lock_file",
    "is_process_running",
    "process_matches_base_dir",
)


def _cmdline_tokens(cmdline: list[str] | None) -> list[str]:
    if not cmdline:
        return []
    return [str(token) for token in cmdline]


def _is_str_list[T](value: list[T] | None) -> TypeGuard[list[str]]:
    if value is None:
        return False
    return all(isinstance(item, str) for item in value)


def _process_cmdline(proc: psutil.Process) -> list[str]:
    try:
        return proc.cmdline()
    except AttributeError:
        cmdline_value = proc.info.get("cmdline")
        return cmdline_value if _is_str_list(cmdline_value) else []
    except psutil.Error:
        return []


def is_process_running(pid: int) -> bool:
    try:
        return bool(psutil.pid_exists(pid))
    except psutil.Error:
        return False


def _process_cwd(proc: psutil.Process) -> str:
    try:
        return proc.cwd()
    except AttributeError:
        return ""
    except psutil.Error:
        return ""


def _process_exe(proc: psutil.Process) -> str:
    try:
        return proc.exe()
    except AttributeError:
        return ""
    except psutil.Error:
        return ""


def _process_name(proc: psutil.Process) -> str:
    try:
        return proc.name()
    except AttributeError:
        return ""
    except psutil.Error:
        return ""


def _markers_describe_soai_instance(
    *,
    cmdline_tokens: list[str],
    cwd: str,
    exe: str,
    name: str,
    base_dir: str,
) -> bool:
    if is_management_process_command(cmdline_tokens):
        return False
    haystacks = [cwd, exe] + [str(arg) for arg in cmdline_tokens]
    if not is_soai_owned_process_markers(haystacks, base_dir=base_dir):
        return False
    if is_soai_instance_process(cmdline_tokens, markers=haystacks, base_dir=base_dir):
        return True
    joined = " ".join(str(token).lower() for token in cmdline_tokens)
    if "soai" in name.lower() and ("backend" in joined or "app.cli.entrypoint" in joined):
        return True
    return False


def process_matches_base_dir(pid: int, base_dir: str) -> bool:
    base_dir_str = os.path.realpath(base_dir)
    try:
        process = psutil.Process(pid)
    except psutil.Error:
        return False
    candidates: list[str] = []
    try:
        candidates.extend(process.cmdline())
    except psutil.Error:
        candidates.append("")
    candidates.append(_process_cwd(process))
    candidates.append(_process_exe(process))
    return is_soai_owned_process_markers(candidates, base_dir=base_dir_str)


def _pid_hint_is_soai_instance(pid: int, base_dir: str) -> bool:
    try:
        process = psutil.Process(pid)
    except psutil.Error:
        return False
    return _markers_describe_soai_instance(
        cmdline_tokens=_cmdline_tokens(_process_cmdline(process)),
        cwd=_process_cwd(process),
        exe=_process_exe(process),
        name=_process_name(process),
        base_dir=base_dir,
    )


def discover_running_instance_pids(
    base_dir: str,
    *,
    logger: logging.Logger,
    pid_hint: int | None = None,
    lock_holder_pids: frozenset[int] = frozenset(),
) -> list[int]:
    current_pid = os.getpid()
    base_dir_str = os.path.realpath(base_dir)
    pids: set[int] = set()
    if pid_hint and pid_hint != current_pid and is_process_running(pid_hint):
        if pid_hint in lock_holder_pids or _pid_hint_is_soai_instance(pid_hint, base_dir_str):
            pids.add(pid_hint)
        else:
            logger.warning(
                "PID file suggests PID %s, but it does not appear to belong to a running SoAI instance in this base directory; refusing automatic termination.",
                pid_hint,
            )
    for proc in psutil.process_iter(attrs=["pid", "cmdline", "cwd", "exe", "name"]):
        pid = proc.info.get("pid")
        if not isinstance(pid, int) or pid <= 0 or pid == current_pid:
            continue
        if _markers_describe_soai_instance(
            cmdline_tokens=_cmdline_tokens(_process_cmdline(proc)),
            cwd=proc.info.get("cwd") or "",
            exe=proc.info.get("exe") or "",
            name=proc.info.get("name") or "",
            base_dir=base_dir_str,
        ):
            pids.add(pid)
    return sorted(pids)


def find_pids_holding_lock_file(lock_file_path: str) -> list[int]:
    resolved_lock = os.path.realpath(lock_file_path)
    pids: set[int] = set()
    for proc in psutil.process_iter(attrs=["pid"]):
        pid = proc.info.get("pid")
        if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
            continue
        try:
            for open_file in proc.open_files():
                try:
                    if os.path.realpath(open_file.path) == resolved_lock:
                        pids.add(pid)
                        break
                except OSError:
                    continue
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except psutil.Error:
            continue
    return sorted(pids)
