"""SoAI - Shell tokenization for MCP shell policy [backend/mcp/tools/shell_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "ShellToken",
    "iter_command_segments",
    "tokenize_shell",
)

_SEPARATOR_TOKENS: frozenset[str] = frozenset({";", "\n", "&&", "||", "|", "&"})


@dataclass(frozen=True, slots=True)
class ShellToken:
    value: str


def tokenize_shell(cmd: str) -> tuple[ShellToken, ...]:
    tokens: list[ShellToken] = []
    current: list[str] = []
    single_quoted = False
    double_quoted = False
    escaped = False
    index = 0
    while index < len(cmd):
        character = cmd[index]
        if escaped:
            current.append(character)
            escaped = False
            index += 1
            continue
        if character == "\\" and not single_quoted:
            escaped = True
            index += 1
            continue
        if character == "'" and not double_quoted:
            single_quoted = not single_quoted
            index += 1
            continue
        if character == '"' and not single_quoted:
            double_quoted = not double_quoted
            index += 1
            continue
        if not single_quoted and not double_quoted:
            if character == "\n":
                _append_token(tokens, current)
                tokens.append(ShellToken("\n"))
                index += 1
                continue
            if character.isspace():
                _append_token(tokens, current)
                index += 1
                continue
            separator_pair = cmd[index : index + 2]
            if separator_pair in {"&&", "||"}:
                _append_token(tokens, current)
                tokens.append(ShellToken(separator_pair))
                index += 2
                continue
            if character in {";", "|", "&", "(", ")", "{", "}"}:
                _append_token(tokens, current)
                tokens.append(ShellToken(character))
                index += 1
                continue
        current.append(character)
        index += 1
    _append_token(tokens, current)
    return tuple(tokens)


def iter_command_segments(tokens: tuple[ShellToken, ...]) -> tuple[tuple[ShellToken, ...], ...]:
    segments: list[tuple[ShellToken, ...]] = []
    current: list[ShellToken] = []
    for token in tokens:
        if token.value in _SEPARATOR_TOKENS:
            if current:
                segments.append(tuple(current))
                current = []
            continue
        current.append(token)
    if current:
        segments.append(tuple(current))
    return tuple(segments)


def _append_token(tokens: list[ShellToken], current: list[str]) -> None:
    if not current:
        return
    value = "".join(current).strip()
    current.clear()
    if value:
        tokens.append(ShellToken(value))
