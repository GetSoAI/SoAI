"""SoAI - Terminal shell detection and environment [backend/terminal/shell.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil

from core.errors.exceptions import StateError
from core.runtime.platform import get_runtime_platform
from terminal.environment import build_terminal_environment

__all__ = (
    "get_default_shell",
    "get_pty_env",
)


def get_default_shell() -> str:
    runtime_platform = get_runtime_platform()
    if runtime_platform.is_windows:
        return os.environ.get("COMSPEC", "powershell.exe")
    configured_shell = os.environ.get("SHELL", "")
    if configured_shell:
        return configured_shell
    bash_path = shutil.which("bash")
    if bash_path is not None:
        return bash_path
    shell_path = shutil.which("sh")
    if shell_path is not None:
        return shell_path
    raise StateError("Default shell not found: bash")


def get_pty_env() -> dict[str, str]:
    return build_terminal_environment(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", ""),
            "PYTHONUNBUFFERED": "1",
        },
    )
