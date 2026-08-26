"""SoAI - MCP utility tool definition: shell_write_stdin [backend/mcp/tools/utility_tool_definitions/shell_write_stdin.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_TERMINAL
from mcp.tools.shell_output_arguments import (
    DEFAULT_SHELL_OUTPUT_PAGE_LINES,
    MAX_SHELL_OUTPUT_PAGE_LINES,
)
from mcp.tools.utility_tool_definitions.shell_output import (
    build_shell_output_schema,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_shell_write_stdin_tool_definitions",)


def build_shell_write_stdin_tool_definitions() -> dict[str, JSONDict]:
    return {
        "shell_write_stdin": {
            "title": "Write StdIn",
            "description": (
                "Write input to a running shell session (started via shell), stream output "
                "deltas during the wait, and return incremental output. COMMAND_BLACKLIST is a "
                "best-effort accidental-misuse check on command names only, not a security "
                "boundary."
            ),
            "icons": [build_tool_icon_entry(ICON_TERMINAL)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "session_id": {
                        "type": "integer",
                        "description": "Session identifier returned by a previous shell call.",
                    },
                    "chars": {
                        "type": "string",
                        "default": "",
                        "description": "Characters to send to the session's stdin. Empty string (default) just reads new output without sending input.",
                    },
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Special key presses to send after chars (e.g. ArrowUp, Enter, Escape, Ctrl+C).",
                    },
                    "cols": {
                        "type": "integer",
                        "description": "Resize terminal columns before sending input (1-500). Must be paired with rows.",
                    },
                    "rows": {
                        "type": "integer",
                        "description": "Resize terminal rows before sending input (1-200). Must be paired with cols.",
                    },
                    "yield_time_ms": {
                        "type": "integer",
                        "default": 250,
                        "description": "Milliseconds to wait for output after sending input (default 250).",
                    },
                    "max_output_tokens": {
                        "type": "integer",
                        "description": "Maximum output length in tokens (multiplied by 4 for character limit).",
                    },
                    "limit": {
                        "type": "integer",
                        "default": DEFAULT_SHELL_OUTPUT_PAGE_LINES,
                        "description": f"Maximum transcript lines to return in this call (max {MAX_SHELL_OUTPUT_PAGE_LINES}).",
                    },
                },
                "required": ["session_id"],
            },
            "output_schema": build_shell_output_schema(),
            "annotations": build_tool_annotation_flags(destructive=True),
        },
    }
