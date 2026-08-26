"""SoAI - Sanitized terminal subprocess environments [backend/terminal/environment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping

from core.runtime.platform import get_runtime_platform
from core.system.subprocess_env import WINDOWS_SUBPROCESS_ENV_NAMES

__all__ = ("build_terminal_environment",)

_POSIX_ENV_KEYS = frozenset(
    {
        "COLORTERM",
        "HOME",
        "LANG",
        "LC_ALL",
        "LOGNAME",
        "PATH",
        "SHELL",
        "TERM",
        "USER",
    },
)


def _copy_selected_environment(
    source: Mapping[str, str],
    allowed_keys: frozenset[str],
) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in source.items():
        if key.upper() in allowed_keys and isinstance(value, str):
            env[key] = value
    return env


def build_terminal_environment(overrides: Mapping[str, str]) -> dict[str, str]:
    runtime_platform = get_runtime_platform()
    allowed_keys = WINDOWS_SUBPROCESS_ENV_NAMES if runtime_platform.is_windows else _POSIX_ENV_KEYS
    env = _copy_selected_environment(os.environ, allowed_keys)
    for key, value in overrides.items():
        if isinstance(value, str):
            env[str(key)] = value
    empty_keys = tuple(key for key, value in env.items() if value == "")
    for key in empty_keys:
        del env[key]
    return env
