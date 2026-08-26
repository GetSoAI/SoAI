"""SoAI - PTY process spawning with validation and platform dispatch [backend/terminal/pty_spawner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.terminal.command_truncation import truncate_shell_command
from core.terminal.pty_validation import clamp_pty_dimensions
from terminal.dependencies import PTYSpawnerDependencies
from terminal.internal_protocols import WindowsPTYProtocol
from terminal.shell import (
    get_default_shell,
    get_pty_env,
)
from terminal.shell_command import PTYShellCommand, resolve_shell_command
from terminal.types import PTYSession

__all__ = ("PTYSpawner",)

OPERATION = "terminal.pty_spawner.spawn"
PTY_SPAWN_OPERATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
)


if sys.platform == "win32":
    from terminal.pty_windows import require_windows_pty_pid, spawn_pty
else:
    from terminal.pty_linux import spawn_pty


class PTYSpawner:

    def __init__(self, deps: PTYSpawnerDependencies) -> None:
        self._base_dir = deps.base_dir
        self._logger = deps.logger

    def spawn(
        self,
        session_id: str,
        cols: int,
        rows: int,
        shell: str | None = None,
    ) -> PTYSession:
        user_specified_shell = shell is not None
        resolved_shell: str
        if user_specified_shell:
            if shell is None:
                raise StateError("PTY shell resolution failed.")
            resolved_shell = shell
        else:
            resolved_shell = get_default_shell()
        shell_command = resolve_shell_command(
            resolved_shell,
            user_specified=user_specified_shell,
        )
        cols, rows = clamp_pty_dimensions(cols, rows)
        env = get_pty_env()
        master_fd, pid = self._spawn_platform_pty(shell_command, cols, rows, env)
        return PTYSession(
            session_id=session_id,
            pid=pid,
            master_fd=master_fd,
            shell_path=shell_command.original,
            cols=cols,
            rows=rows,
        )

    def _spawn_platform_pty(
        self,
        shell_command: PTYShellCommand,
        cols: int,
        rows: int,
        env: dict[str, str],
    ) -> tuple[int | WindowsPTYProtocol, int]:
        try:
            if sys.platform == "win32":
                pty_obj = spawn_pty(shell_command, cols, rows, self._base_dir, env)
                return (pty_obj, require_windows_pty_pid(pty_obj))
            return spawn_pty(shell_command, cols, rows, self._base_dir, env)
        except PTY_SPAWN_OPERATION_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Failed to spawn PTY",
                operation=OPERATION,
            )
            raise StateError(
                f"Failed to create PTY session: {truncate_shell_command(shell_command.original)}",
            ) from exception
