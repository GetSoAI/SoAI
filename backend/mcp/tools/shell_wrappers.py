"""SoAI - Command wrapper normalization for MCP shell policy [backend/mcp/tools/shell_wrappers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from mcp.tools.shell_tokens import ShellToken

__all__ = ("unwrap_command_wrappers",)

_CONTROL_TOKENS: frozenset[str] = frozenset({"(", ")", "{", "}"})
_SUDO_OPTIONS_WITH_ARG: frozenset[str] = frozenset(
    {
        "-a",
        "-C",
        "-g",
        "-h",
        "-p",
        "-r",
        "-t",
        "-T",
        "-u",
        "--askpass",
        "--chroot",
        "--close-from",
        "--group",
        "--host",
        "--login-class",
        "--prompt",
        "--role",
        "--type",
        "--user",
    },
)
_ENV_OPTIONS_WITH_ARG: frozenset[str] = frozenset({"-C", "-u", "--chdir", "--unset"})
_EXEC_OPTIONS_WITH_ARG: frozenset[str] = frozenset({"-a"})
_NICE_OPTIONS_WITH_ARG: frozenset[str] = frozenset({"-n", "--adjustment"})
_STDBUF_OPTIONS_WITH_ARG: frozenset[str] = frozenset(
    {"-e", "-i", "-o", "--error", "--input", "--output"},
)
_TIME_OPTIONS_WITH_ARG: frozenset[str] = frozenset({"-f", "-o", "--format", "--output"})
_TIMEOUT_OPTIONS_WITH_ARG: frozenset[str] = frozenset({"-k", "-s", "--kill-after", "--signal"})


def unwrap_command_wrappers(tokens: tuple[ShellToken, ...]) -> tuple[ShellToken, ...]:
    remaining = _skip_assignments(_skip_control_tokens(tokens))
    while remaining:
        remaining = _skip_assignments(remaining)
        if not remaining:
            return remaining
        head = os.path.basename(remaining[0].value.strip()).lower()
        if head == "sudo":
            remaining = _unwrap_sudo(remaining[1:])
            continue
        if head == "env":
            remaining = _skip_assignments(
                _unwrap_simple_options(remaining[1:], options_with_arg=_ENV_OPTIONS_WITH_ARG),
            )
            continue
        if head == "command":
            remaining = _unwrap_simple_options(remaining[1:], options_with_arg=frozenset())
            continue
        if head == "exec":
            remaining = _unwrap_simple_options(
                remaining[1:],
                options_with_arg=_EXEC_OPTIONS_WITH_ARG,
            )
            continue
        if head == "builtin":
            remaining = remaining[1:]
            continue
        if head == "nohup":
            remaining = remaining[1:]
            continue
        if head == "nice":
            remaining = _unwrap_simple_options(
                remaining[1:],
                options_with_arg=_NICE_OPTIONS_WITH_ARG,
            )
            continue
        if head == "stdbuf":
            remaining = _unwrap_simple_options(
                remaining[1:],
                options_with_arg=_STDBUF_OPTIONS_WITH_ARG,
            )
            continue
        if head == "time":
            remaining = _unwrap_simple_options(
                remaining[1:],
                options_with_arg=_TIME_OPTIONS_WITH_ARG,
            )
            continue
        if head == "timeout":
            remaining = _unwrap_timeout(remaining[1:])
            continue
        return remaining
    return remaining


def _skip_control_tokens(tokens: tuple[ShellToken, ...]) -> tuple[ShellToken, ...]:
    remaining = tokens
    while remaining and remaining[0].value in _CONTROL_TOKENS:
        remaining = remaining[1:]
    return remaining


def _is_assignment_token(token: str) -> bool:
    if "=" not in token:
        return False
    name, _value = token.split("=", 1)
    if not name:
        return False
    if not (name[0].isalpha() or name[0] == "_"):
        return False
    return all(character.isalnum() or character == "_" for character in name[1:])


def _skip_assignments(tokens: tuple[ShellToken, ...]) -> tuple[ShellToken, ...]:
    remaining = tokens
    while remaining and _is_assignment_token(remaining[0].value.strip()):
        remaining = remaining[1:]
    return remaining


def _unwrap_sudo(tokens: tuple[ShellToken, ...]) -> tuple[ShellToken, ...]:
    remaining = _unwrap_simple_options(tokens, options_with_arg=_SUDO_OPTIONS_WITH_ARG)
    if remaining and remaining[0].value == "--":
        return remaining[1:]
    return remaining


def _unwrap_timeout(tokens: tuple[ShellToken, ...]) -> tuple[ShellToken, ...]:
    remaining = _unwrap_simple_options(tokens, options_with_arg=_TIMEOUT_OPTIONS_WITH_ARG)
    if remaining and not remaining[0].value.strip().startswith("-"):
        return remaining[1:]
    return remaining


def _unwrap_simple_options(
    tokens: tuple[ShellToken, ...],
    *,
    options_with_arg: frozenset[str],
) -> tuple[ShellToken, ...]:
    remaining = tokens
    while remaining:
        token = remaining[0].value.strip()
        if not token:
            remaining = remaining[1:]
            continue
        if token == "--":
            return remaining[1:]
        if not token.startswith("-"):
            return remaining
        remaining = remaining[1:]
        if token in options_with_arg and remaining:
            remaining = remaining[1:]
    return remaining
