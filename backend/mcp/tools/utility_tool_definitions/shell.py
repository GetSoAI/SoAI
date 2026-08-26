"""SoAI - MCP utility tool definition: shell [backend/mcp/tools/utility_tool_definitions/shell.py]"""
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

__all__ = ("build_shell_tool_definitions",)


def build_shell_tool_definitions() -> dict[str, JSONDict]:
    return {
        "shell": {
            "title": "Shell",
            "description": (
                "Run a real host shell command. The process starts in workspace_path or workdir, "
                "but command execution is not filesystem-sandboxed. Foreground commands stream "
                "output during yield_time_ms, then either return exit_code when complete or return "
                "status=running with session_id for shell_write_stdin/polling while the tracked "
                "PTY session continues server-side. COMMAND_BLACKLIST provides best-effort "
                "accidental-misuse checks; it is not a security boundary because interpreters "
                "and executed programs retain the caller's terminal authority."
            ),
            "icons": [build_tool_icon_entry(ICON_TERMINAL)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "cmd": {
                        "type": "string",
                        "description": "Shell command to execute.",
                    },
                    "workdir": {
                        "type": "string",
                        "description": (
                            "Working directory under workspace_path "
                            "(or an absolute path within it)."
                        ),
                    },
                    "shell": {"type": "string", "description": "Shell executable (e.g. bash)."},
                    "login": {
                        "type": "boolean",
                        "default": True,
                        "description": "Run as a login shell, loading user profile (default true).",
                    },
                    "tty": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "Allocate a pseudo-TTY for interactive programs (e.g. top, vim) "
                            "or to keep a session open. When true, returns a session_id for "
                            "shell_write_stdin. Default false."
                        ),
                    },
                    "run_in_background": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "When true, return immediately while the tracked PTY session keeps "
                            "running server-side; the tool-call activity stays live, receives "
                            "output as it is produced, and is delivered with retained output "
                            "and exit_code when the session exits or errors. Use shell_write_stdin "
                            "to send input or press keys. Default false."
                        ),
                    },
                    "stream_output": {
                        "type": "boolean",
                        "default": True,
                        "description": (
                            "When true, stream output deltas for yield_time_ms. If the process "
                            "is still running, return status=running and keep the session alive "
                            "for shell_write_stdin/polling. Background mode accepts this flag but "
                            "still returns immediately. Defaults true for foreground non-TTY "
                            "commands and false for background or persistent TTY sessions."
                        ),
                    },
                    "yield_time_ms": {
                        "type": "integer",
                        "default": 10000,
                        "description": (
                            "Milliseconds to wait for output before returning (default 10000). "
                            "For stream_output=true this bounds the foreground wait, not the "
                            "process lifetime."
                        ),
                    },
                    "cols": {
                        "type": "integer",
                        "description": "Terminal columns for the PTY session (1-500). Must be paired with rows.",
                    },
                    "rows": {
                        "type": "integer",
                        "description": "Terminal rows for the PTY session (1-200). Must be paired with cols.",
                    },
                    "max_output_tokens": {
                        "type": "integer",
                        "description": (
                            "Maximum output length in tokens (multiplied by 4 for character "
                            "limit). Defaults to internal limit."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "default": DEFAULT_SHELL_OUTPUT_PAGE_LINES,
                        "description": f"Maximum transcript lines to return in this call (max {MAX_SHELL_OUTPUT_PAGE_LINES}).",
                    },
                },
                "required": ["cmd"],
            },
            "output_schema": build_shell_output_schema(),
            "annotations": build_tool_annotation_flags(destructive=True),
        },
    }
