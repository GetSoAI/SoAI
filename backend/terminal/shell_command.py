"""SoAI - Terminal shell command resolution [backend/terminal/shell_command.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import shlex
import shutil
import sys
from dataclasses import dataclass

from core.errors.exceptions import StateError, ValidationError

__all__ = (
    "PTYShellCommand",
    "resolve_shell_command",
)


@dataclass(frozen=True, slots=True)
class PTYShellCommand:
    original: str
    executable_path: str
    argv: tuple[str, ...]


def resolve_shell_command(shell: str, *, user_specified: bool) -> PTYShellCommand:
    try:
        shell_parts = _split_shell_command(shell)
    except ValidationError as exception:
        if user_specified:
            raise
        raise StateError(f"Default shell is invalid: {shell}") from exception
    executable_name = _strip_matching_quotes(shell_parts[0])
    executable_path = shutil.which(executable_name)
    if executable_path is None:
        if user_specified:
            raise ValidationError(f"Shell not found: {executable_name}")
        raise StateError(f"Default shell not found: {executable_name}")
    argv = tuple([executable_path, *shell_parts[1:]])
    return PTYShellCommand(original=shell, executable_path=executable_path, argv=argv)


def _split_shell_command(shell: str) -> list[str]:
    try:
        shell_parts = shlex.split(shell, posix=sys.platform != "win32")
    except ValueError as exception:
        raise ValidationError(f"Shell command is invalid: {exception}") from exception
    if not shell_parts:
        raise ValidationError("Shell command must not be empty.")
    return [str(shell_part) for shell_part in shell_parts]


def _strip_matching_quotes(value: str) -> str:
    if len(value) < 2:
        return value
    first_char = value[0]
    if first_char not in {'"', "'"}:
        return value
    if value[-1] != first_char:
        return value
    return value[1:-1]
