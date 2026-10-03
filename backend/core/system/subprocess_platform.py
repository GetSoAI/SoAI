"""SoAI - Platform-specific subprocess option resolution [backend/core/system/subprocess_platform.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import errno
import ntpath
import os
from collections.abc import Mapping, Sequence
from ctypes import wintypes
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.filesystem.component_limits import filesystem_component_size
from core.filesystem.path_coercion import (
    normalize_filesystem_path,
    remove_windows_path_namespace,
)
from core.platform.os import is_windows
from core.system.windows_ctypes import last_windows_error, load_kernel32

if TYPE_CHECKING:
    from core.system.protocols import StartupInfoProtocol

__all__ = (
    "SubprocessPaths",
    "WINDOWS_CREATE_BREAKAWAY_FROM_JOB",
    "WINDOWS_CREATE_NEW_PROCESS_GROUP",
    "WINDOWS_CREATE_NO_WINDOW",
    "WINDOWS_DETACHED_PROCESS",
    "resolve_subprocess_creationflags",
    "resolve_subprocess_environment",
    "resolve_subprocess_paths",
    "resolve_subprocess_startupinfo",
    "resolve_windows_process_path",
    "windows_isolated_process_creationflags",
    "windows_no_window_creationflags",
)

WINDOWS_DETACHED_PROCESS: int = 0x00000008
WINDOWS_CREATE_NEW_PROCESS_GROUP: int = 0x00000200
WINDOWS_CREATE_NO_WINDOW: int = 0x08000000
WINDOWS_CREATE_BREAKAWAY_FROM_JOB: int = 0x01000000


@dataclass(frozen=True, slots=True)
class SubprocessPaths:
    executable: str | None
    working_directory: str | None


def resolve_windows_process_path(
    path: str,
    *,
    directory: bool,
    preserve_executable_namespace: bool = False,
    prefer_short_name: bool = False,
) -> str:
    logical = remove_windows_path_namespace(path)
    prefix_size = (6 if logical.startswith("\\\\") else 4) if preserve_executable_namespace else 0
    maximum_size = (259 if not directory or logical.endswith("\\") else 258) - prefix_size
    if not prefer_short_name and filesystem_component_size(logical) <= maximum_size:
        return normalize_filesystem_path(logical) if preserve_executable_namespace else logical
    kernel = load_kernel32()
    short_path = ctypes.create_unicode_buffer(32768)
    get_short_path = kernel.GetShortPathNameW
    get_short_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    get_short_path.restype = wintypes.DWORD
    length = get_short_path(normalize_filesystem_path(logical), short_path, len(short_path))
    if not length:
        raise OSError(
            errno.EIO,
            f"Windows process path resolution failed (Windows error {last_windows_error()}).",
            path,
        )
    physical = remove_windows_path_namespace(short_path.value)
    prefix_size = (6 if physical.startswith("\\\\") else 4) if preserve_executable_namespace else 0
    maximum_size = (259 if not directory or physical.endswith("\\") else 258) - prefix_size
    if length >= len(short_path) or filesystem_component_size(physical) > maximum_size:
        raise OSError(
            errno.ENAMETOOLONG,
            "This Windows process path has no usable existing short filesystem name. Choose a shorter path.",
            path,
        )
    return normalize_filesystem_path(physical) if preserve_executable_namespace else physical


def resolve_subprocess_paths(command: Sequence[str], cwd: str | None) -> SubprocessPaths:
    if not is_windows():
        return SubprocessPaths(executable=None, working_directory=cwd)
    executable = None
    if command and ntpath.isabs(command[0]) and filesystem_component_size(command[0]) >= 260:
        executable = resolve_windows_process_path(
            command[0],
            directory=False,
            preserve_executable_namespace=ntpath.basename(command[0]).lower()
            in ("python.exe", "pythonw.exe"),
        )
    current = os.path.abspath(cwd) if cwd is not None else os.getcwd()
    resolved = resolve_windows_process_path(current, directory=True)
    return SubprocessPaths(
        executable=executable, working_directory=cwd if resolved == current else resolved
    )


def resolve_subprocess_creationflags(creationflags: int | None) -> int:
    if not is_windows():
        return 0
    return int(creationflags or 0)


def resolve_subprocess_environment(environment: Mapping[str, str] | None) -> dict[str, str] | None:
    if not is_windows():
        return dict(environment) if environment is not None else None
    resolved = dict(os.environ if environment is None else environment)
    for name, value in resolved.items():
        if name.upper() in ("TEMP", "TMP", "TMPDIR") and value:
            resolved[name] = resolve_windows_process_path(value, directory=True)
    return resolved


def resolve_subprocess_startupinfo(
    startupinfo: StartupInfoProtocol | None,
) -> StartupInfoProtocol | None:
    if not is_windows():
        return None
    return startupinfo


def windows_no_window_creationflags() -> int:
    return resolve_subprocess_creationflags(WINDOWS_CREATE_NO_WINDOW)


def windows_isolated_process_creationflags() -> int:
    return resolve_subprocess_creationflags(
        WINDOWS_CREATE_NEW_PROCESS_GROUP | WINDOWS_CREATE_NO_WINDOW,
    )
