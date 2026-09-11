"""SoAI - NVIDIA display environment detection [backend/hardware/vendors/nvidia/smi_display_environment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import os
import socket
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.errors.exception_logging import log_handled_exception
from core.filesystem.open_files import open_text
from core.system.commands import run_argv_capture
from core.system.process_launcher import SUBPROCESS_RECOVERABLE_EXCEPTIONS

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "detect_display_environment",
    "enumerate_displays",
    "display_target_occupied",
    "validate_display",
    "display_process_environment",
    "DisplaySearchResult",
    "DisplaySearchStatus",
)

OPERATION_HARDWARE_NVIDIA_DETECT_DISPLAY_ENVIRONMENT = "hardware_nvidia.detect_display_environment"
X11_SOCKET_DIR_PARTS = ("tmp", ".X11-unix")
DISPLAY_MANAGER_RUNTIME_DIRS = ("gdm", "sddm", "lightdm")
SDDM_RUNTIME_DIR_PARTS = ("run", "sddm")


class DisplaySearchStatus(Enum):
    USABLE = "usable"
    NO_DISPLAY = "no_display"
    DEADLINE = "deadline"
    TOOL_UNAVAILABLE = "tool_unavailable"
    ACCESS_FAILURE = "access_failure"


@dataclass(frozen=True, slots=True)
class DisplaySearchResult:
    status: DisplaySearchStatus
    display: str | None = None
    xauthority: str | None = None


def display_process_environment(display: str, xauthority: str | None) -> dict[str, str]:
    environment = os.environ.copy()
    environment["DISPLAY"] = display
    environment.pop("XAUTHORITY", None)
    if xauthority is not None:
        environment["XAUTHORITY"] = xauthority
    return environment


def detect_display_environment(
    logger: LoggerProtocol,
    deadline: MonotonicDeadline | None = None,
) -> DisplaySearchResult:
    discovery_deadline = deadline_after(4.0)
    if deadline is not None:
        discovery_deadline = MonotonicDeadline(
            min(discovery_deadline.deadline_monotonic, deadline.deadline_monotonic)
        )
    failure = DisplaySearchStatus.NO_DISPLAY
    try:
        enumerated_displays = enumerate_displays()
        displays = enumerated_displays or (":0",)
        xauthorities = _candidate_xauthorities(discovery_deadline)
        for display in displays:
            if discovery_deadline.expired():
                return DisplaySearchResult(DisplaySearchStatus.DEADLINE)
            if not _display_may_listen(display, discovery_deadline):
                continue
            for xauthority in xauthorities:
                result = validate_display(display, xauthority, discovery_deadline)
                if result.status in (
                    DisplaySearchStatus.USABLE,
                    DisplaySearchStatus.TOOL_UNAVAILABLE,
                ):
                    return result
                if result.status in (
                    DisplaySearchStatus.ACCESS_FAILURE,
                    DisplaySearchStatus.DEADLINE,
                ):
                    failure = result.status
    except SUBPROCESS_RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to inspect NVIDIA display environment.",
            operation=OPERATION_HARDWARE_NVIDIA_DETECT_DISPLAY_ENVIRONMENT,
            level="debug",
        )
        return DisplaySearchResult(DisplaySearchStatus.ACCESS_FAILURE)
    if discovery_deadline.remaining_seconds() < 1:
        return DisplaySearchResult(DisplaySearchStatus.DEADLINE)
    return DisplaySearchResult(failure)


def _display_may_listen(display: str, deadline: MonotonicDeadline) -> bool:
    socket_path = os.path.join(_x11_socket_dir(), f"X{display[1:]}")
    for address in (socket_path, f"\0{socket_path}"):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                remaining = deadline.remaining_seconds()
                if remaining <= 0:
                    return False
                connection.settimeout(min(0.2, remaining))
                connection.connect(address)
            return True
        except OSError as exception:
            if exception.errno not in (errno.ECONNREFUSED, errno.ENOENT):
                return True
    return False


def display_target_occupied(display: str, deadline: MonotonicDeadline) -> bool:
    socket_path = os.path.join(_x11_socket_dir(), f"X{display[1:]}")
    for address in (socket_path, f"\0{socket_path}"):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                remaining = deadline.remaining_seconds()
                if remaining <= 0:
                    return True
                connection.settimeout(min(0.2, remaining))
                connection.connect(address)
            return True
        except OSError as exception:
            if exception.errno not in (errno.ECONNREFUSED, errno.ENOENT):
                return True
    return False


def validate_display(
    display: str,
    xauthority: str | None,
    deadline: MonotonicDeadline,
) -> DisplaySearchResult:
    timeout = int(min(2.0, deadline.remaining_seconds()))
    if timeout < 1:
        return DisplaySearchResult(DisplaySearchStatus.DEADLINE)
    result = run_argv_capture(
        ["nvidia-settings", "-c", display, "-q", "gpus"],
        env=display_process_environment(display, xauthority),
        timeout=timeout,
    )
    if result.return_code == 127:
        return DisplaySearchResult(DisplaySearchStatus.TOOL_UNAVAILABLE)
    if result.return_code == 124:
        return DisplaySearchResult(DisplaySearchStatus.DEADLINE)
    output = (result.stdout + result.stderr).lower()
    if result.return_code == 0 and "[gpu:" in output:
        return DisplaySearchResult(DisplaySearchStatus.USABLE, display, xauthority)
    if result.return_code != 0:
        return DisplaySearchResult(DisplaySearchStatus.ACCESS_FAILURE)
    return DisplaySearchResult(DisplaySearchStatus.NO_DISPLAY)


def enumerate_displays() -> tuple[str, ...]:
    displays: list[str] = []
    try:
        socket_names = os.listdir(_x11_socket_dir())
    except OSError:
        socket_names = []
    for socket_name in sorted(socket_names):
        if not socket_name.startswith("X"):
            continue
        suffix = socket_name[1:]
        if suffix.isdigit():
            displays.append(f":{suffix}")
    return tuple(displays)


def _candidate_xauthorities(deadline: MonotonicDeadline | None = None) -> tuple[str | None, ...]:
    candidates: list[str | None] = []
    for path in _xauthorities_from_running_xservers(deadline):
        _append_unique(candidates, path)
    for path in _xauthorities_from_runtime_dirs(deadline):
        _append_unique(candidates, path)
    env_xauthority = os.environ.get("XAUTHORITY", "")
    if env_xauthority:
        _append_unique(candidates, env_xauthority)
    candidates.append(None)
    return tuple(candidates)


def _xauthorities_from_running_xservers(deadline: MonotonicDeadline | None = None) -> list[str]:
    paths: list[str] = []
    try:
        process_ids = os.listdir("/proc")
    except OSError:
        return paths
    for process_id in process_ids:
        if deadline is not None and deadline.expired():
            return paths
        if not process_id.isdigit():
            continue
        cmdline = _read_proc_cmdline(process_id)
        if not cmdline:
            continue
        executable = os.path.basename(cmdline[0])
        if "Xorg" not in executable and executable != "X":
            continue
        auth_path = _auth_argument(cmdline)
        if auth_path is not None and os.path.exists(auth_path) and auth_path not in paths:
            paths.append(auth_path)
    return paths


def _read_proc_cmdline(process_id: str) -> list[str]:
    cmdline_path = os.path.join("/proc", process_id, "cmdline")
    try:
        with open_text(cmdline_path, encoding="utf-8", errors="replace") as handle:
            raw = handle.read()
    except OSError:
        return []
    return [token for token in raw.split("\x00") if token]


def _auth_argument(cmdline: list[str]) -> str | None:
    for index, token in enumerate(cmdline):
        if token == "-auth" and index + 1 < len(cmdline):
            return cmdline[index + 1]
    return None


def _xauthorities_from_runtime_dirs(deadline: MonotonicDeadline | None = None) -> list[str]:
    paths: list[str] = []
    sddm_runtime_dir = _sddm_runtime_dir()
    for entry in _list_directory(sddm_runtime_dir):
        if entry.startswith("xauth"):
            paths.append(os.path.join(sddm_runtime_dir, entry))
    for runtime_root in _runtime_search_roots():
        if deadline is not None and deadline.expired():
            return paths
        for user_id_dir in _list_directory(runtime_root):
            if deadline is not None and deadline.expired():
                return paths
            user_runtime_path = os.path.join(runtime_root, user_id_dir)
            if not os.path.isdir(user_runtime_path):
                continue
            for display_manager in DISPLAY_MANAGER_RUNTIME_DIRS:
                xauthority_path = os.path.join(user_runtime_path, display_manager, "Xauthority")
                if os.path.exists(xauthority_path):
                    paths.append(xauthority_path)
    return paths


def _runtime_search_roots() -> tuple[str, ...]:
    runtime_root = os.environ.get("XDG_RUNTIME_DIR", "")
    runtime_parent = os.path.dirname(runtime_root) if runtime_root else ""
    candidates: list[str] = []
    if runtime_parent:
        candidates.append(runtime_parent)
    candidates.append(os.path.join(os.sep, "run", "user"))
    roots: list[str] = []
    for candidate in candidates:
        if candidate and os.path.isdir(candidate) and candidate not in roots:
            roots.append(candidate)
    return tuple(roots)


def _list_directory(path: str) -> list[str]:
    try:
        return os.listdir(path)
    except OSError:
        return []


def _x11_socket_dir() -> str:
    return os.path.join(os.path.sep, *X11_SOCKET_DIR_PARTS)


def _sddm_runtime_dir() -> str:
    return os.path.join(os.path.sep, *SDDM_RUNTIME_DIR_PARTS)


def _append_unique(candidates: list[str | None], path: str) -> None:
    if path and path not in candidates and os.path.exists(path):
        candidates.append(path)
