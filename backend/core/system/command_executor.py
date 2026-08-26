"""SoAI - Command execution via core.system.commands.run_argv_capture [backend/core/system/command_executor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import shlex
import shutil
from collections.abc import Sequence
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.logging.protocols import LoggerProtocol
from core.platform.os import is_windows
from core.system.commands import CommandResult, run_argv_capture

__all__ = (
    "CommandExecutor",
    "CommandExecutorDependencies",
)


@dataclass(frozen=True, slots=True)
class CommandExecutorDependencies:
    executor_logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="CommandExecutorDependencies",
            executor_logger=self.executor_logger,
        )


class CommandExecutor:
    __slots__ = ("_sudo_missing_logged", "logger")

    def __init__(self, deps: CommandExecutorDependencies) -> None:
        self.logger: LoggerProtocol = deps.executor_logger
        self._sudo_missing_logged: bool = False

    def execute(
        self,
        command: str | Sequence[str],
        *,
        timeout: int,
        shell: bool,
        use_sudo: bool,
        stdin_text: str | None = None,
    ) -> CommandResult:
        if shell:
            raise ValidationError("Shell execution is not permitted for terminal commands.")
        argv: list[str]
        if isinstance(command, str) and (not shell):
            argv = shlex.split(command, posix=not is_windows())
        else:
            argv = [str(part) for part in command]
        if use_sudo and (not is_windows()):
            sudo_available = shutil.which("sudo") is not None
            if not sudo_available:
                if not self._sudo_missing_logged:
                    self.logger.warning(
                        "sudo is required for privileged operations but is not installed.",
                    )
                    self._sudo_missing_logged = True
                return CommandResult(stdout="", return_code=127, stderr="sudo unavailable")
            argv = ["sudo", *argv]
        return run_argv_capture(
            argv,
            timeout=timeout,
            stdin_text=stdin_text,
            check=False,
        )
