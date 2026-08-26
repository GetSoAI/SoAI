"""SoAI - MCP shell argument parsing [backend/mcp/tools/shell_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.mcp.argument_validation import (
    require_no_unknown_keys,
    require_non_empty_string_value,
)
from core.types.json import JSONDict
from core.validation.booleans import parse_bool_flag_with_default
from mcp.tools.argument_scalars import parse_int
from mcp.tools.error import MCPToolError, build_invalid_params_error
from mcp.tools.shell_output_arguments import parse_shell_output_limit
from mcp.tools.shell_session_support import (
    DEFAULT_SHELL_YIELD_MS,
    parse_optional_bounded_int,
    resolve_max_output_chars,
    validate_shell_value,
)

__all__ = (
    "ShellToolRequest",
    "parse_shell_tool_request",
)


@dataclass(frozen=True, slots=True)
class ShellToolRequest:
    cmd: str
    login: bool
    tty: bool
    run_in_background: bool
    stream_output: bool
    yield_time_ms: int
    max_output_chars: int
    output_limit: int
    shell_exe: str
    cols: int
    rows: int


_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "cmd",
        "workdir",
        "shell",
        "login",
        "tty",
        "run_in_background",
        "stream_output",
        "yield_time_ms",
        "max_output_tokens",
        "limit",
        "cols",
        "rows",
    },
)


def parse_shell_tool_request(
    arguments: JSONDict,
) -> ShellToolRequest:
    require_no_unknown_keys(
        arguments,
        _ALLOWED_KEYS,
        build_error=build_invalid_params_error,
        message=lambda invalid_keys: (
            f"shell received unknown parameter(s): {', '.join(invalid_keys)}"
        ),
    )
    if "cmd" not in arguments:
        raise MCPToolError(-32602, "Missing required parameter: cmd")
    cmd = require_non_empty_string_value(
        arguments["cmd"],
        build_error=build_invalid_params_error,
        type_message="cmd must be a non-empty string",
        empty_message="cmd must be a non-empty string",
    )

    login = parse_bool_flag_with_default(arguments.get("login"), default=True)
    tty = parse_bool_flag_with_default(arguments.get("tty"), default=False)
    run_in_background = parse_bool_flag_with_default(
        arguments.get("run_in_background"),
        default=False,
    )
    stream_output = parse_bool_flag_with_default(
        arguments.get("stream_output"),
        default=not tty and not run_in_background,
    )
    if run_in_background:
        stream_output = False

    yield_time_ms = parse_int(
        arguments.get("yield_time_ms"),
        default=DEFAULT_SHELL_YIELD_MS,
        min_value=0,
        max_value=600_000,
    )
    cols = parse_optional_bounded_int(arguments.get("cols"), key="cols", min_value=1, max_value=500)
    rows = parse_optional_bounded_int(arguments.get("rows"), key="rows", min_value=1, max_value=200)
    if (cols is None) != (rows is None):
        raise MCPToolError(-32602, "cols and rows must be provided together")
    resolved_cols = cols if cols is not None else 120
    resolved_rows = rows if rows is not None else 40
    shell_exe = validate_shell_value(arguments.get("shell")) or "bash"
    max_output_chars = resolve_max_output_chars(arguments.get("max_output_tokens"))
    output_limit = parse_shell_output_limit(arguments.get("limit"))

    return ShellToolRequest(
        cmd=cmd,
        login=login,
        tty=tty,
        run_in_background=run_in_background,
        stream_output=stream_output,
        yield_time_ms=yield_time_ms,
        max_output_chars=max_output_chars,
        output_limit=output_limit,
        shell_exe=shell_exe,
        cols=resolved_cols,
        rows=resolved_rows,
    )
