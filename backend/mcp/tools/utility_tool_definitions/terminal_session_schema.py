"""SoAI - MCP utility tool definition fragments for terminal sessions [backend/mcp/tools/utility_tool_definitions/terminal_session_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_terminal_session_output_properties",
    "build_terminal_session_output_schema",
)


def build_terminal_session_output_properties() -> JSONDict:
    return {
        "output": {"type": "string"},
        "session_id": {"type": "integer"},
        "exit_code": {"type": "integer"},
        "status": {"type": "string", "enum": ["running"]},
    }


def build_terminal_session_output_schema() -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": build_terminal_session_output_properties(),
    }
