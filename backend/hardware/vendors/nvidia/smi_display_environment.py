"""SoAI - NVIDIA display environment detection [backend/hardware/vendors/nvidia/smi_display_environment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.filesystem.open_files import open_text
from core.system.commands import run_argv_capture
from core.system.process_launcher import SUBPROCESS_RECOVERABLE_EXCEPTIONS

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("detect_display_environment",)

OPERATION_HARDWARE_NVIDIA_DETECT_DISPLAY_ENVIRONMENT = "hardware_nvidia.detect_display_environment"
X11_SOCKET_DIR_PARTS = ("tmp", ".X11-unix")
DISPLAY_MANAGER_RUNTIME_DIRS = ("gdm", "sddm", "lightdm")
SDDM_RUNTIME_DIR_PARTS = ("run", "sddm")


def detect_display_environment(logger: LoggerProtocol) -> JSONDict:
    try:
        displays = _active_displays()
        xauthorities = _candidate_xauthorities()
        for display in displays:
            for xauthority in xauthorities:
                if _resolves_nvidia_gpu(display, xauthority):
                    return {
                        "has_display_manager": True,
                        "display": display,
                        "xauthority": xauthority,
                        "needs_own_xserver": False,
                    }
    except SUBPROCESS_RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to detect display environment for NVIDIA settings (non-critical).",
            operation=OPERATION_HARDWARE_NVIDIA_DETECT_DISPLAY_ENVIRONMENT,
            level="debug",
        )
    return {
        "has_display_manager": False,
        "display": ":1",
        "xauthority": None,
        "needs_own_xserver": True,
    }


def _resolves_nvidia_gpu(display: str, xauthority: str | None) -> bool:
    env = os.environ.copy()
    env["DISPLAY"] = display
    if xauthority is not None:
        env["XAUTHORITY"] = xauthority
    elif "XAUTHORITY" in env:
        del env["XAUTHORITY"]
    result = run_argv_capture(
        ["nvidia-settings", "-c", display, "-q", "gpus"],
        env=env,
        timeout=8,
    )
    if result.return_code != 0:
        return False
    return "[gpu:" in (result.stdout + result.stderr).lower()


def _active_displays() -> tuple[str, ...]:
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
    if not displays:
        displays.append(":0")
    return tuple(displays)


def _candidate_xauthorities() -> tuple[str | None, ...]:
    candidates: list[str | None] = []
    for path in _xauthorities_from_running_xservers():
        _append_unique(candidates, path)
    for path in _xauthorities_from_runtime_dirs():
        _append_unique(candidates, path)
    env_xauthority = os.environ.get("XAUTHORITY", "")
    if env_xauthority:
        _append_unique(candidates, env_xauthority)
    candidates.append(None)
    return tuple(candidates)


def _xauthorities_from_running_xservers() -> list[str]:
    paths: list[str] = []
    try:
        process_ids = os.listdir("/proc")
    except OSError:
        return paths
    for process_id in process_ids:
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


def _xauthorities_from_runtime_dirs() -> list[str]:
    paths: list[str] = []
    sddm_runtime_dir = _sddm_runtime_dir()
    for entry in _list_directory(sddm_runtime_dir):
        if entry.startswith("xauth"):
            paths.append(os.path.join(sddm_runtime_dir, entry))
    for runtime_root in _runtime_search_roots():
        for user_id_dir in _list_directory(runtime_root):
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
