"""SoAI - Install command argument parsing [backend/core/bootstrap/install_arguments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = (
    "INSTALL_COMMANDS",
    "ParsedInstallArguments",
    "contains_install_command",
    "contains_install_command_or_option",
    "parse_install_arguments",
)

INSTALL_COMMANDS: frozenset[str] = frozenset(
    {
        "install",
        "--install",
        "-install",
        "install-deps",
        "--install-deps",
        "-install-deps",
    },
)
INSTALL_OPTIONS: frozenset[str] = frozenset(
    {
        "--target",
        "-target",
        "--silent",
        "-silent",
        "--json-events",
        "-json-events",
        "--status-file",
        "-status-file",
    },
)


@dataclass(frozen=True, slots=True)
class ParsedInstallArguments:
    command: str | None
    target: str
    target_explicit: bool
    silent: bool
    json_events: bool
    status_file: str
    install_options_used: bool
    passthrough_args: tuple[str, ...]


def contains_install_command(argv: Sequence[str]) -> bool:
    for arg in argv:
        if arg in INSTALL_COMMANDS:
            return True
    return False


def contains_install_command_or_option(argv: Sequence[str]) -> bool:
    for arg in argv:
        if arg in INSTALL_COMMANDS or arg in INSTALL_OPTIONS:
            return True
        if arg.startswith("--target=") or arg.startswith("--status-file="):
            return True
    return False


def parse_install_arguments(
    argv: Sequence[str],
    *,
    default_target: str,
    current_directory: str,
) -> ParsedInstallArguments:
    command: str | None = None
    target = ""
    target_explicit = False
    silent = False
    json_events = False
    status_file = ""
    install_options_used = False
    passthrough_args: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in INSTALL_COMMANDS:
            if command is not None:
                raise ValueError("Only one SoAI install command can be specified.")
            command = _normalize_command(arg)
            index += 1
        elif arg in {"--target", "-target"}:
            value = _read_option_value(argv, index, "--target")
            target = value
            target_explicit = True
            install_options_used = True
            index += 2
        elif arg.startswith("--target="):
            target = _require_clean_value("--target", arg.removeprefix("--target="))
            target_explicit = True
            install_options_used = True
            index += 1
        elif arg in {"--silent", "-silent"}:
            silent = True
            install_options_used = True
            index += 1
        elif arg in {"--json-events", "-json-events"}:
            json_events = True
            install_options_used = True
            index += 1
        elif arg in {"--status-file", "-status-file"}:
            value = _read_option_value(argv, index, "--status-file")
            status_file = _normalize_status_file(value, current_directory=current_directory)
            install_options_used = True
            index += 2
        elif arg.startswith("--status-file="):
            value = _require_clean_value("--status-file", arg.removeprefix("--status-file="))
            status_file = _normalize_status_file(value, current_directory=current_directory)
            install_options_used = True
            index += 1
        else:
            passthrough_args.append(arg)
            index += 1
    if not target:
        target = default_target
    if command not in {"install", "install-deps"} and install_options_used:
        raise ValueError("Install options require the install or install-deps command.")
    if command == "install-deps" and target_explicit:
        raise ValueError("--target is only valid with the install command.")
    return ParsedInstallArguments(
        command=command,
        target=target,
        target_explicit=target_explicit,
        silent=silent,
        json_events=json_events,
        status_file=status_file,
        install_options_used=install_options_used,
        passthrough_args=tuple(passthrough_args),
    )


def _normalize_command(arg: str) -> str:
    if arg in {"install", "--install", "-install"}:
        return "install"
    return "install-deps"


def _read_option_value(argv: Sequence[str], index: int, option: str) -> str:
    if index + 1 >= len(argv):
        raise ValueError(f"{option} requires a non-empty value.")
    return _require_clean_value(option, argv[index + 1])


def _require_clean_value(option: str, value: str) -> str:
    if not value:
        raise ValueError(f"{option} requires a non-empty value.")
    if "\n" in value or "\r" in value or "\t" in value:
        raise ValueError(f"{option} must not contain control characters.")
    return value


def _normalize_status_file(value: str, *, current_directory: str) -> str:
    clean_value = _require_clean_value("--status-file", value)
    if os.path.isabs(clean_value):
        return os.path.abspath(clean_value)
    return os.path.abspath(os.path.join(current_directory, clean_value))
