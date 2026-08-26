"""SoAI - Host command execution and process management primitives [backend/core/system/commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypedDict

from core.platform.os import is_linux, is_macos, is_windows
from core.system.protocols import (
    CommandExecutorProtocol,
    StartupInfoProtocol,
)
from core.system.subprocess_platform import (
    resolve_subprocess_creationflags,
    resolve_subprocess_startupinfo,
    windows_no_window_creationflags,
)

__all__ = (
    "CommandResult",
    "ProcessInfo",
    "SystemActionCommand",
    "build_system_action_command",
    "execute_system_action",
    "kill_process_native",
    "run_argv_capture",
)


class ProcessInfo(TypedDict):
    pid: int
    name: str
    username: str | None
    cpu_percent: float
    memory_mb: float
    create_time: float


@dataclass(frozen=True, slots=True)
class CommandResult:
    stdout: str
    return_code: int
    stderr: str


def run_argv_capture(
    argv: Sequence[str],
    *,
    timeout: int,
    stdin_text: str | None = None,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    encoding: str | None = None,
    errors: str | None = None,
    startupinfo: StartupInfoProtocol | None = None,
    creationflags: int | None = None,
    check: bool = False,
) -> CommandResult:
    try:
        process = subprocess.run(
            [str(part) for part in argv],
            shell=False,
            capture_output=True,
            text=True,
            input=stdin_text,
            encoding=encoding,
            errors=errors,
            timeout=timeout,
            check=False,
            env=dict(env) if env is not None else None,
            cwd=cwd,
            startupinfo=resolve_subprocess_startupinfo(startupinfo),
            creationflags=(
                resolve_subprocess_creationflags(creationflags)
                if creationflags is not None
                else windows_no_window_creationflags()
            ),
        )
        result = CommandResult(
            stdout=process.stdout,
            return_code=process.returncode,
            stderr=process.stderr,
        )
    except subprocess.TimeoutExpired:
        result = CommandResult(stdout="", return_code=124, stderr=f"Timeout after {timeout}s")
    except OSError as exception:
        result = CommandResult(
            stdout="",
            return_code=127,
            stderr=f"Command not found: {exception!s}",
        )
    if check and result.return_code != 0:
        raise subprocess.CalledProcessError(
            result.return_code,
            [str(part) for part in argv],
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


@dataclass(frozen=True, slots=True)
class SystemActionCommand:
    argv: list[str]
    os_name: str
    action: str


def build_system_action_command(
    action: str,
    args: list[str] | None = None,
) -> SystemActionCommand | tuple[bool, str]:
    action = str(action or "").strip()
    if not action:
        return (False, "System action is required.")
    base_args = [str(value) for value in (args or [])]
    if is_windows():
        os_name = "Windows"
    elif is_macos():
        os_name = "Darwin"
    elif is_linux():
        os_name = "Linux"
    else:
        os_name = "Unknown"
    cmd_map: dict[str, dict[str, list[str]]] = {
        "Windows": {
            "shutdown": ["shutdown"],
            "reboot": ["shutdown"],
            "hibernate": ["shutdown", "/h"],
        },
        "Darwin": {
            "shutdown": ["shutdown", "-h"],
            "reboot": ["shutdown", "-r"],
            "suspend": ["pmset", "sleepnow"],
        },
        "Linux": {
            "shutdown": ["systemctl", "poweroff"],
            "reboot": ["systemctl", "reboot"],
            "suspend": ["systemctl", "suspend"],
            "hibernate": ["systemctl", "hibernate"],
        },
    }
    base_command = cmd_map.get(os_name, {}).get(action)
    if not base_command:
        return (False, f"Action '{action}' not supported on {os_name}")
    command = list(base_command)
    if os_name == "Darwin":
        if action in {"shutdown", "reboot"}:
            if len(base_args) > 1:
                return (
                    False,
                    f"Action '{action}' supports at most one argument on {os_name}",
                )
            command.append(base_args[0] if base_args else "now")
        elif base_args:
            return (False, f"Action '{action}' does not accept arguments on {os_name}")
    else:
        command.extend(base_args)
    return SystemActionCommand(argv=command, os_name=os_name, action=action)


def execute_system_action(
    executor: CommandExecutorProtocol,
    action: str,
    args: list[str] | None = None,
    use_sudo: bool = False,
) -> tuple[bool, str]:
    build_result = build_system_action_command(action, args)
    if isinstance(build_result, tuple):
        return build_result
    result = executor.execute(build_result.argv, timeout=5, shell=False, use_sudo=use_sudo)
    action_name = build_result.action
    if result.return_code == 0:
        return (True, f"{action_name.title()} initiated")
    return (
        False,
        f"{action_name.title()} failed: {result.stderr.strip() or 'Unknown error'}",
    )


def kill_process_native(
    executor: CommandExecutorProtocol,
    pid: int,
    signal_to_send: int,
    use_sudo: bool,
) -> tuple[bool, str]:
    command = (
        ["taskkill", "/F", "/PID", str(pid)]
        if is_windows()
        else ["kill", f"-{signal_to_send}", str(pid)]
    )
    result = executor.execute(command, timeout=5, shell=False, use_sudo=use_sudo)
    if result.return_code == 0:
        return (
            True,
            (
                f"Process {pid} terminated."
                if is_windows()
                else f"Signal {signal_to_send} sent to process {pid}."
            ),
        )
    return (False, f"Failed to kill process {pid}: {result.stderr}")
