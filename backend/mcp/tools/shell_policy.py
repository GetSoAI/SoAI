"""SoAI - Shell policy validation for MCP tools [backend/mcp/tools/shell_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from mcp.tools.error import MCPToolError
from mcp.tools.shell_tokens import (
    ShellToken,
    iter_command_segments,
    tokenize_shell,
)
from mcp.tools.shell_wrappers import unwrap_command_wrappers

__all__ = ("enforce_shell_policy",)

_SHELL_COMMAND_EXECUTABLES: frozenset[str] = frozenset({"bash", "dash", "ksh", "sh", "zsh"})
_SHELL_EVAL_COMMANDS: frozenset[str] = frozenset({"eval"})
_SHELL_OPTIONS_WITH_ARG: frozenset[str] = frozenset(
    {"-O", "+O", "-o", "+o", "--init-file", "--rcfile"},
)
_RECURSION_LIMIT = 8


def enforce_shell_policy(
    cmd: str,
    *,
    blacklist: tuple[str, ...],
    tool_name: str,
) -> None:
    normalized_entries: set[str] = set()
    for entry in blacklist:
        normalized_entry = _normalize_command_reference(entry)
        if normalized_entry:
            normalized_entries.add(normalized_entry)
    if not normalized_entries:
        return
    blacklist_set = frozenset(normalized_entries)
    blacklist_basenames = frozenset(os.path.basename(entry) for entry in blacklist_set)
    blocked = _find_blacklisted_command(
        cmd,
        blacklist_set=blacklist_set,
        blacklist_basenames=blacklist_basenames,
        depth=0,
    )
    if blocked:
        raise MCPToolError(
            -32603,
            f"{tool_name} blocked by configuration (TOOLS.MCP.SHELL.COMMAND_BLACKLIST). Blocked command: {blocked!r}.",
        )


def _find_blacklisted_command(
    cmd: str,
    *,
    blacklist_set: frozenset[str],
    blacklist_basenames: frozenset[str],
    depth: int,
) -> str | None:
    if depth > _RECURSION_LIMIT:
        return None
    normalized_cmd = cmd.strip()
    if not normalized_cmd:
        return None
    for segment in iter_command_segments(tokenize_shell(normalized_cmd)):
        blocked = _inspect_segment(
            segment,
            blacklist_set=blacklist_set,
            blacklist_basenames=blacklist_basenames,
            depth=depth,
        )
        if blocked:
            return blocked
    return None


def _inspect_segment(
    segment: tuple[ShellToken, ...],
    *,
    blacklist_set: frozenset[str],
    blacklist_basenames: frozenset[str],
    depth: int,
) -> str | None:
    tokens = unwrap_command_wrappers(segment)
    if not tokens:
        return None
    blocked = _match_blacklist(tokens[0].value.strip(), blacklist_set, blacklist_basenames)
    if blocked:
        return blocked
    shell_payload = _extract_shell_command_payload(tokens)
    if shell_payload is None:
        return None
    return _find_blacklisted_command(
        shell_payload,
        blacklist_set=blacklist_set,
        blacklist_basenames=blacklist_basenames,
        depth=depth + 1,
    )


def _match_blacklist(
    command_token: str,
    blacklist_set: frozenset[str],
    blacklist_basenames: frozenset[str],
) -> str | None:
    normalized = _normalize_command_reference(command_token)
    if not normalized:
        return None
    basename = os.path.basename(normalized)
    if normalized in blacklist_set or basename in blacklist_set:
        return basename or normalized
    if basename in blacklist_basenames:
        return basename
    return None


def _normalize_command_reference(value: str) -> str:
    normalized = value.strip().lower().rstrip("/")
    return normalized or value.strip().lower()


def _extract_shell_command_payload(tokens: tuple[ShellToken, ...]) -> str | None:
    command_reference = _normalize_command_reference(tokens[0].value)
    command_basename = os.path.basename(command_reference)
    if command_basename in _SHELL_EVAL_COMMANDS:
        return " ".join(token.value for token in tokens[1:])
    if command_basename not in _SHELL_COMMAND_EXECUTABLES:
        return None
    index = 1
    while index < len(tokens):
        token = tokens[index].value.strip()
        if token == "--":
            index += 1
            continue
        if _is_shell_command_payload_option(token):
            payload_index = index + 1
            if payload_index < len(tokens):
                return tokens[payload_index].value
            return ""
        if token in _SHELL_OPTIONS_WITH_ARG:
            index += 2
            continue
        if not _is_shell_option_token(token):
            return None
        index += 1
    return None


def _is_shell_option_token(token: str) -> bool:
    return token.startswith("-") or token in {"+O", "+o"}


def _is_shell_command_payload_option(token: str) -> bool:
    return token == "-c" or (
        token.startswith("-") and not token.startswith("--") and "c" in token[1:]
    )
