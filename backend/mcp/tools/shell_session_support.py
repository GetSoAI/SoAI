"""SoAI - MCP shell session support [backend/mcp/tools/shell_session_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shlex
from typing import TYPE_CHECKING

from core.logging.protocols import LoggerProtocol
from core.mcp.argument_numbers import parse_integer_like_value
from mcp.tools.argument_scalars import parse_optional_int_strict
from mcp.tools.error import MCPToolError
from mcp.tools.shell_session_cleanup import (
    ShellSessionCleanupDeps,
    finalize_shell_terminal_session,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "build_interactive_shell",
    "build_non_tty_shell_command",
    "cleanup_pruned_shell_sessions",
    "load_shell_blacklist",
    "parse_optional_bounded_int",
    "parse_session_id",
    "resolve_max_output_chars",
    "resolve_requested_workdir",
    "validate_shell_value",
)

DEFAULT_SHELL_YIELD_MS: int = 10_000
DEFAULT_WRITE_YIELD_MS: int = 250
DEFAULT_MAX_OUTPUT_CHARS: int = 20_000


def resolve_max_output_chars(max_output_tokens: JSONValue) -> int:
    if isinstance(max_output_tokens, bool):
        return DEFAULT_MAX_OUTPUT_CHARS
    if isinstance(max_output_tokens, int):
        return max(1, min(int(max_output_tokens) * 4, DEFAULT_MAX_OUTPUT_CHARS))
    if isinstance(max_output_tokens, float) and max_output_tokens.is_integer():
        return max(1, min(int(max_output_tokens) * 4, DEFAULT_MAX_OUTPUT_CHARS))
    if isinstance(max_output_tokens, str) and max_output_tokens.strip().isdigit():
        return max(1, min(int(max_output_tokens.strip()) * 4, DEFAULT_MAX_OUTPUT_CHARS))
    return DEFAULT_MAX_OUTPUT_CHARS


def validate_shell_value(shell: JSONValue) -> str | None:
    if shell is None:
        return None
    if not isinstance(shell, str):
        raise MCPToolError(-32602, "shell must be a string when provided.")
    normalized = shell.strip()
    if not normalized:
        return None
    if any(ch.isspace() for ch in normalized):
        raise MCPToolError(-32602, "shell must not contain whitespace.")
    return normalized


def resolve_requested_workdir(arguments: JSONDict) -> str | None:
    workdir_value = arguments.get("workdir")
    if isinstance(workdir_value, str) and workdir_value.strip():
        return workdir_value.strip()
    return None


def parse_session_id(raw_session_id: JSONValue) -> int:
    parsed = parse_integer_like_value(
        raw_session_id,
        build_error=lambda message: MCPToolError(-32602, message),
        integer_message="session_id must be an integer (int, integer string, or integer float)",
    )
    if isinstance(raw_session_id, str) and not raw_session_id.strip().isdigit():
        raise MCPToolError(
            -32602,
            "session_id must be an integer (int, integer string, or integer float)",
        )
    return parsed


def parse_optional_bounded_int(
    value: JSONValue,
    *,
    key: str,
    min_value: int,
    max_value: int,
) -> int | None:
    return parse_optional_int_strict(
        value,
        field_name=key,
        min_value=min_value,
        max_value=max_value,
        integer_message=f"{key} must be an integer when provided",
        range_message=(
            f"{key} must be between {min_value} and {max_value} (inclusive) when provided"
        ),
    )


def build_non_tty_shell_command(
    *,
    shell_exe: str,
    login: bool,
    workdir: str,
    cmd: str,
) -> str:
    normalized_shell = shell_exe.strip() or "bash"
    shell_name = os.path.basename(normalized_shell).strip().lower()
    command_to_run = f"cd {shlex.quote(workdir)} && {cmd}"
    if shell_name in {"bash", "zsh"}:
        return f"{normalized_shell} {'-lc' if login else '-c'} {shlex.quote(command_to_run)}"
    return f"{normalized_shell} -c {shlex.quote(command_to_run)}"


def build_interactive_shell(*, shell_exe: str, login: bool) -> str | None:
    normalized_shell = shell_exe.strip() if shell_exe else ""
    if not normalized_shell:
        return None
    shell_name = os.path.basename(normalized_shell).strip().lower()
    if login and shell_name in {"bash", "zsh"}:
        return f"{normalized_shell} -l"
    return normalized_shell


async def cleanup_pruned_shell_sessions(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    logger: LoggerProtocol,
    operation: str,
) -> int:
    sessions = utility_tools.runtime_sessions.pop_shell_sessions_pending_terminal_close()
    closed_count = 0
    cleanup_deps = ShellSessionCleanupDeps(
        runtime_sessions=utility_tools.runtime_sessions,
        terminal=utility_tools.terminal,
        logger=logger,
    )
    for session in sessions:
        finalized = await finalize_shell_terminal_session(
            cleanup_deps,
            operation=operation,
            shell_session_id=session.session_id,
            terminal_session_id=session.terminal_session_id,
            session=session,
        )
        if finalized:
            closed_count += 1
    return closed_count


def load_shell_blacklist(utility_tools: MCPUtilityToolsProtocol) -> tuple[str, ...]:
    raw = utility_tools.config.get("TOOLS.MCP.SHELL.COMMAND_BLACKLIST", [])
    if isinstance(raw, list | tuple | set | frozenset):
        entries = [str(entry).strip() for entry in raw if str(entry).strip()]
    elif isinstance(raw, str) and raw.strip():
        entries = [raw.strip()]
    else:
        entries = []
    normalized = [entry.lower() for entry in entries if entry]
    return tuple(normalized)
