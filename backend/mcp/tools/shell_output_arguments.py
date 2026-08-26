"""SoAI - MCP shell output pagination argument policy [backend/mcp/tools/shell_output_arguments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.argument_scalars import parse_int

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "DEFAULT_SHELL_OUTPUT_PAGE_LINES",
    "MAX_SHELL_OUTPUT_PAGE_LINES",
    "parse_shell_output_limit",
    "parse_shell_output_offset",
)

DEFAULT_SHELL_OUTPUT_PAGE_LINES: int = 250
MAX_SHELL_OUTPUT_PAGE_LINES: int = 1000


def parse_shell_output_limit(value: JSONValue) -> int:
    return parse_int(
        value,
        default=DEFAULT_SHELL_OUTPUT_PAGE_LINES,
        min_value=1,
        max_value=MAX_SHELL_OUTPUT_PAGE_LINES,
    )


def parse_shell_output_offset(value: JSONValue) -> int:
    return parse_int(value, default=1, min_value=1, max_value=100_000_000)
