"""SoAI - Playwright driver command operands [backend/core/browser/playwright_driver_commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.errors.exceptions import StateError
from core.filesystem.path_coercion import coerce_path, remove_windows_path_namespace
from core.platform.os import is_windows
from core.serialization.json_parsing import parse_json_str_list
from core.system.commands import run_argv_capture
from core.system.subprocess_platform import resolve_windows_process_path
from core.timing.constants import CONTROL_TIMEOUT_SEC
from core.validation.strings import coerce_required_non_empty_str

__all__ = (
    "PlaywrightInstallCommand",
    "build_playwright_install_command",
    "resolve_playwright_driver_command",
    "resolve_playwright_driver_environment",
)

_DRIVER_PATH_PROBE = (
    "import json\n"
    "from playwright._impl._driver import compute_driver_executable, get_driver_env\n"
    "environment = get_driver_env()\n"
    'print(json.dumps([*compute_driver_executable(), environment["PW_LANG_NAME"], environment["PW_LANG_NAME_VERSION"], environment["PW_CLI_DISPLAY_VERSION"]]))\n'
)


@dataclass(frozen=True, slots=True)
class PlaywrightInstallCommand:
    argv: list[str]
    environment: dict[str, str]


def resolve_playwright_driver_command(
    executable: str, entrypoint: str, arguments: Sequence[str]
) -> list[str]:
    executable = coerce_path(executable)
    entrypoint = coerce_path(entrypoint)
    if is_windows():
        executable = remove_windows_path_namespace(executable)
        entrypoint = remove_windows_path_namespace(entrypoint)
    return [executable, entrypoint, *arguments]


def build_playwright_install_command(*, python_executable: str) -> PlaywrightInstallCommand:
    if not is_windows():
        return PlaywrightInstallCommand(
            [python_executable, "-m", "playwright", "install", "chromium"], {}
        )
    result = run_argv_capture(
        [python_executable, "-c", _DRIVER_PATH_PROBE],
        encoding="utf-8",
        errors="replace",
        timeout=CONTROL_TIMEOUT_SEC,
        check=True,
    )

    paths = parse_json_str_list(result.stdout, field="Playwright driver paths")
    if len(paths) != 5:
        raise StateError("Playwright driver discovery must identify its executable and entrypoint.")
    return PlaywrightInstallCommand(
        resolve_playwright_driver_command(paths[0], paths[1], ("install", "chromium")),
        {
            "PW_LANG_NAME": coerce_required_non_empty_str(paths[2], label="Playwright language"),
            "PW_LANG_NAME_VERSION": coerce_required_non_empty_str(
                paths[3], label="Playwright language version"
            ),
            "PW_CLI_DISPLAY_VERSION": coerce_required_non_empty_str(
                paths[4], label="Playwright display version"
            ),
        },
    )


def resolve_playwright_driver_environment(environment: Mapping[str, str]) -> dict[str, str]:
    resolved = dict(environment)
    if is_windows():
        for name in ("PLAYWRIGHT_BROWSERS_PATH", "TEMP", "TMP", "TMPDIR"):
            path = resolved.get(name, "")
            if path and not (name == "PLAYWRIGHT_BROWSERS_PATH" and path == "0"):
                resolved[name] = resolve_windows_process_path(
                    os.path.abspath(path), directory=True, prefer_short_name=True
                )
    return resolved
