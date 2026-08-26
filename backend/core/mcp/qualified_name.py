"""SoAI - MCP qualified tool name encoding and decoding helpers [backend/core/mcp/qualified_name.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.errors.exceptions import ValidationError

__all__ = (
    "MCP_TOOL_NAME_SEPARATOR",
    "decode_qualified_tool_name",
    "encode_qualified_tool_name",
    "is_valid_qualified_server_id",
)

MCP_TOOL_NAME_SEPARATOR = "__"
_VALID_SERVER_ID_PATTERN = r"^[A-Za-z0-9._:-]+$"


def is_valid_qualified_server_id(server_id: str) -> bool:
    normalized = server_id.strip()
    if not normalized:
        return False
    if MCP_TOOL_NAME_SEPARATOR in normalized:
        return False
    if any(char.isspace() for char in normalized):
        return False
    if "/" in normalized or "\\" in normalized:
        return False
    if re.fullmatch(_VALID_SERVER_ID_PATTERN, normalized) is None:
        return False
    return True


def encode_qualified_tool_name(server_id: str, tool_name: str) -> str:
    normalized_server_id = server_id.strip()
    if not is_valid_qualified_server_id(normalized_server_id):
        raise ValidationError("Invalid MCP server id for qualified tool naming.")
    return f"{normalized_server_id}{MCP_TOOL_NAME_SEPARATOR}{tool_name}"


def decode_qualified_tool_name(qualified_name: str) -> tuple[str | None, str]:
    if MCP_TOOL_NAME_SEPARATOR in qualified_name:
        parts = qualified_name.split(MCP_TOOL_NAME_SEPARATOR, 1)
        return (parts[0], parts[1])
    return (None, qualified_name)
