"""SoAI - Interactive shell input projection policy [backend/mcp/tools/shell_interactive_input_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.terminal.key_sequences import encode_key_sequence
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "ShellInputPayload",
    "ShellInputProjection",
    "parse_shell_input",
    "project_shell_input",
)

_MAX_BUFFER_CHARS = 8192


@dataclass(frozen=True, slots=True)
class ShellInputProjection:
    complete_lines: tuple[str, ...]
    tail: str


@dataclass(frozen=True, slots=True)
class ShellInputPayload:
    chars: str
    encoded_keys: tuple[bytes, ...]
    normalized_keys: tuple[str, ...]


def parse_shell_input(
    chars_value: JSONValue | None,
    keys_value: JSONValue | None,
) -> ShellInputPayload:
    if chars_value is None:
        chars_value = ""
    if not isinstance(chars_value, str):
        raise MCPToolError(-32602, "chars must be a string")
    if keys_value is None:
        return ShellInputPayload(chars=chars_value, encoded_keys=(), normalized_keys=())
    if not isinstance(keys_value, list):
        raise MCPToolError(-32602, "keys must be an array when provided")
    if len(keys_value) > 256:
        raise MCPToolError(-32602, "keys must contain at most 256 entries")
    encoded_keys: list[bytes] = []
    normalized_keys: list[str] = []
    for entry in keys_value:
        if not isinstance(entry, str) or not entry.strip():
            raise MCPToolError(-32602, "keys entries must be non-empty strings")
        normalized_key = entry.strip()
        try:
            encoded = encode_key_sequence(normalized_key)
        except ValidationError as exception:
            raise MCPToolError(-32602, str(exception)) from exception
        encoded_keys.append(encoded)
        normalized_keys.append(normalized_key)
    return ShellInputPayload(
        chars=chars_value,
        encoded_keys=tuple(encoded_keys),
        normalized_keys=tuple(normalized_keys),
    )


def project_shell_input(
    *,
    current_buffer: str,
    chars: str,
    keys: tuple[str, ...],
) -> ShellInputProjection:
    tail = current_buffer
    completed: list[str] = []
    normalized_chars = chars.replace("\r\n", "\n").replace("\r", "\n")
    for character in normalized_chars:
        if character == "\n":
            if tail:
                completed.append(tail)
            tail = ""
        elif character in {"\x08", "\x7f"}:
            tail = tail[:-1]
        elif character.isprintable():
            tail += character
    for key in keys:
        if key == "Enter":
            if tail:
                completed.append(tail)
            tail = ""
        elif key == "Backspace":
            tail = tail[:-1]
    if len(tail) > _MAX_BUFFER_CHARS:
        tail = tail[-_MAX_BUFFER_CHARS:]
    return ShellInputProjection(complete_lines=tuple(completed), tail=tail)
