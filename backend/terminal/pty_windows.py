"""SoAI - Windows PTY implementation [backend/terminal/pty_windows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import signal
import sys
from collections.abc import Callable
from subprocess import list2cmdline

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.constants import SHORT_POLL_INTERVAL_SEC
from core.timing.sleep import sleep_seconds
from terminal.internal_protocols import WindowsPTYProtocol
from terminal.shell_command import PTYShellCommand

__all__ = (
    "close_pty",
    "read_pty",
    "require_windows_pty_pid",
    "spawn_pty",
)

LOGGER_NAME = "SoAI.terminal.pty_windows"
OPERATION_PTY_WINDOWS_SPAWN_PTY = "terminal.pty_windows.spawn_pty"
OPERATION_TERMINAL_PTY_WINDOWS_READ_PTY = "terminal.pty_windows.read_pty"
WINDOWS_PTY_OPERATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
    RuntimeError,
    ValueError,
)


if sys.platform == "win32":
    try:
        from winpty import PTY
    except (ImportError, OSError):
        WINPTY_FACTORY: Callable[[int, int], WindowsPTYProtocol] | None = None
    else:

        def _spawn_winpty(cols: int, rows: int) -> WindowsPTYProtocol:
            return PTY(cols, rows)

        WINPTY_FACTORY = _spawn_winpty
else:
    WINPTY_FACTORY = None


def _create_pty_instance(
    pty_factory: Callable[[int, int], WindowsPTYProtocol],
    cols: int,
    rows: int,
) -> WindowsPTYProtocol:
    return pty_factory(cols, rows)


def spawn_pty(
    shell_command: PTYShellCommand,
    cols: int,
    rows: int,
    cwd: str,
    env: dict[str, str],
) -> WindowsPTYProtocol:
    if sys.platform != "win32":
        raise StateError("Windows PTY is only supported on Windows.")
    if WINPTY_FACTORY is None:
        raise StateError("pywinpty PTY is unavailable. Cannot create PTY on Windows.")
    if not callable(WINPTY_FACTORY):
        raise StateError("pywinpty PTY is not callable. Cannot create PTY on Windows.")
    pty_process = _create_pty_instance(WINPTY_FACTORY, cols, rows)
    try:
        spawned = _spawn_windows_pty_process(
            pty_process,
            shell_command=shell_command,
            cwd=cwd,
            env=env,
        )
    except WINDOWS_PTY_OPERATION_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to spawn Windows PTY.",
            operation=OPERATION_PTY_WINDOWS_SPAWN_PTY,
        )
        raise StateError(f"Failed to spawn Windows PTY: {exception}") from exception
    if not spawned:
        raise StateError("Windows PTY spawn failed.")
    require_windows_pty_pid(pty_process)
    return pty_process


def _spawn_windows_pty_process(
    pty_process: WindowsPTYProtocol,
    *,
    shell_command: PTYShellCommand,
    cwd: str,
    env: dict[str, str],
) -> bool:
    spawn = pty_process.spawn
    return spawn(
        shell_command.executable_path,
        _build_windows_cmdline(shell_command),
        cwd=cwd,
        env=_build_windows_env_block(env),
    )


def require_windows_pty_pid(pty_obj: WindowsPTYProtocol) -> int:
    pid = pty_obj.pid
    if not isinstance(pid, int) or pid <= 0:
        raise StateError("Windows PTY spawn did not return a process id.")
    return pid


def read_pty(pty_obj: WindowsPTYProtocol, size: int = 4096) -> bytes | None:
    _ = size
    logger = get_logger(LOGGER_NAME)
    try:
        data = pty_obj.read(blocking=False)
        if data:
            return data.encode("utf-8", errors="replace")
        if _is_windows_pty_finished(pty_obj):
            return None
        return b""
    except WINDOWS_PTY_OPERATION_EXCEPTIONS as exception:
        if _is_windows_pty_finished(pty_obj):
            return None
        log_handled_exception(
            logger,
            exception,
            message="Failed to read from Windows PTY (non-critical).",
            operation=OPERATION_TERMINAL_PTY_WINDOWS_READ_PTY,
            level="debug",
        )
        return b""


def close_pty(pty_obj: WindowsPTYProtocol) -> None:
    cancellation_failure: Exception | None = None
    try:
        pty_obj.cancel_io()
    except WINDOWS_PTY_OPERATION_EXCEPTIONS as exception:
        cancellation_failure = exception
    _terminate_pty_process(pty_obj)
    if cancellation_failure is not None:
        raise StateError(
            "Windows PTY resources could not be fully closed.",
            operation="terminal.pty_windows.close_pty",
        ) from cancellation_failure


def _build_windows_cmdline(shell_command: PTYShellCommand) -> str | None:
    arguments = list(shell_command.argv[1:])
    if not arguments:
        return None
    return f" {list2cmdline(arguments)}"


def _build_windows_env_block(env: dict[str, str]) -> str:
    entries: list[str] = []
    for key, value in sorted(env.items(), key=lambda item: item[0].upper()):
        if "\0" in key or "\0" in value:
            raise StateError("Windows PTY environment contains an invalid NUL byte.")
        entries.append(f"{key}={value}")
    env_payload = "\0".join(entries)
    return f"{env_payload}\0"


def _is_windows_pty_finished(pty_obj: WindowsPTYProtocol) -> bool:
    try:
        return pty_obj.iseof() or (not pty_obj.isalive())
    except WINDOWS_PTY_OPERATION_EXCEPTIONS:
        return True


def _terminate_pty_process(pty_obj: WindowsPTYProtocol) -> None:
    pid = pty_obj.pid
    if not isinstance(pid, int) or pid <= 0:
        raise StateError("Windows PTY process id is invalid during shutdown.")
    if not _is_windows_pty_alive(pty_obj):
        return
    try:
        _terminate_process(pid)
    except WINDOWS_PTY_OPERATION_EXCEPTIONS as exception:
        raise StateError(
            "Windows PTY process could not be terminated.",
            operation="terminal.pty_windows.close_pty",
            details={"pid": pid},
        ) from exception
    for _ in range(20):
        if not _is_windows_pty_alive(pty_obj):
            return
        sleep_seconds(SHORT_POLL_INTERVAL_SEC)
    raise StateError(
        "Windows PTY process remained alive after termination.",
        operation="terminal.pty_windows.close_pty",
        details={"pid": pid},
    )


def _terminate_process(pid: int) -> None:
    os.kill(pid, signal.SIGTERM)


def _is_windows_pty_alive(pty_obj: WindowsPTYProtocol) -> bool:
    try:
        return pty_obj.isalive()
    except WINDOWS_PTY_OPERATION_EXCEPTIONS as exception:
        raise StateError("Windows PTY process state could not be inspected.") from exception
