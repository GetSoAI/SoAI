"""SoAI - MCP utility tool: shell_write_stdin [backend/mcp/tools/shell_write_stdin.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.state.access import AccessAction
from mcp.tools.access_control import require_tool_action
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.argument_scalars import parse_int
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.shell_interactive_input_policy import (
    parse_shell_input,
    project_shell_input,
)
from mcp.tools.shell_output_arguments import parse_shell_output_limit
from mcp.tools.shell_output_payloads import build_shell_incremental_output_payload
from mcp.tools.shell_policy import enforce_shell_policy
from mcp.tools.shell_session_cleanup import (
    ShellSessionCleanupDeps,
    close_shell_session_resources,
)
from mcp.tools.shell_session_support import (
    DEFAULT_WRITE_YIELD_MS,
    cleanup_pruned_shell_sessions,
    load_shell_blacklist,
    parse_optional_bounded_int,
    parse_session_id,
    resolve_max_output_chars,
)
from mcp.tools.shell_write_stdin_completion import (
    complete_closed_shell_write_stdin_session,
    complete_exited_shell_write_stdin_session,
    drain_shell_write_stdin_output,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_shell_write_stdin",)

LOGGER_NAME_MCP_TOOLS_WRITESTDIN = "SoAI.mcp.tools.writestdin"
OPERATION_MCP_TOOLS_WRITESTDIN_BLACKLIST_CLEANUP = (
    "mcp.tools.shell_session_tools.tool_shell_write_stdin.blacklist_cleanup"
)
OPERATION_MCP_TOOLS_WRITESTDIN_CLOSE_CLEANUP = (
    "mcp.tools.shell_session_tools.tool_shell_write_stdin.close_cleanup"
)
_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "session_id",
        "chars",
        "keys",
        "cols",
        "rows",
        "yield_time_ms",
        "max_output_tokens",
        "limit",
    },
)


async def tool_shell_write_stdin(
    utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict
) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    session_id = parse_session_id(get_arg(arguments, "session_id"))
    await require_tool_action(
        utility_tools,
        action=AccessAction.TERMINAL_USE,
        tool_name="shell_write_stdin",
    )

    input_payload = parse_shell_input(arguments.get("chars"), arguments.get("keys"))
    cols_value = arguments.get("cols")
    rows_value = arguments.get("rows")
    cols = parse_optional_bounded_int(cols_value, key="cols", min_value=1, max_value=500)
    rows = parse_optional_bounded_int(rows_value, key="rows", min_value=1, max_value=200)
    if (cols is None) != (rows is None):
        raise MCPToolError(-32602, "cols and rows must be provided together when resizing")
    yield_time_ms = parse_int(
        arguments.get("yield_time_ms"),
        default=DEFAULT_WRITE_YIELD_MS,
        min_value=0,
        max_value=600_000,
    )
    max_output_chars = resolve_max_output_chars(arguments.get("max_output_tokens"))
    output_limit = parse_shell_output_limit(arguments.get("limit"))
    logger = get_logger(LOGGER_NAME_MCP_TOOLS_WRITESTDIN)
    cleanup_deps = ShellSessionCleanupDeps(
        runtime_sessions=utility_tools.runtime_sessions,
        terminal=utility_tools.terminal,
        logger=logger,
    )
    await cleanup_pruned_shell_sessions(
        utility_tools,
        logger=logger,
        operation="mcp.tools.shell_session_tools.tool_shell_write_stdin.pruned_cleanup",
    )

    if not utility_tools.config.get_bool("TOOLS.MCP.SHELL.ENABLED"):
        owner_key = utility_tools.runtime_sessions.current_owner_key()
        session = utility_tools.runtime_sessions.get_shell_session(session_id)
        if session is not None and session.owner_key == owner_key:
            await close_shell_session_resources(
                cleanup_deps,
                operation=OPERATION_MCP_TOOLS_WRITESTDIN_CLOSE_CLEANUP,
                shell_session_id=session.session_id,
                terminal_session_id=session.terminal_session_id,
            )
        raise MCPToolError(
            -32603,
            "shell_write_stdin is disabled because shell sessions are disabled by configuration (TOOLS.MCP.SHELL.ENABLED=false). Set TOOLS.MCP.SHELL.ENABLED=true in config.yaml to enable shell/shell_write_stdin.",
        )

    owner_key = utility_tools.runtime_sessions.current_owner_key()
    session = utility_tools.runtime_sessions.get_shell_session(session_id)
    await cleanup_pruned_shell_sessions(
        utility_tools,
        logger=logger,
        operation="mcp.tools.shell_session_tools.tool_shell_write_stdin.pruned_cleanup",
    )
    if session is None or session.owner_key != owner_key:
        raise MCPToolError(-32602, f"Unknown session_id: {session_id}")
    if session.exit_code is not None:
        return await complete_exited_shell_write_stdin_session(
            utility_tools,
            cleanup_deps,
            session=session,
            yield_time_ms=yield_time_ms,
            max_output_chars=max_output_chars,
            output_limit=output_limit,
            exit_code=int(session.exit_code),
            operation=OPERATION_MCP_TOOLS_WRITESTDIN_CLOSE_CLEANUP,
        )
    async with session.stdin_lock:
        current_session = utility_tools.runtime_sessions.get_shell_session(session_id)
        if current_session is None or current_session is not session:
            raise MCPToolError(-32602, f"Unknown session_id: {session_id}")
        if current_session.owner_key != owner_key:
            raise MCPToolError(-32602, f"Unknown session_id: {session_id}")
        exited_while_waiting = session.exit_code
        if exited_while_waiting is None:
            blacklist = load_shell_blacklist(utility_tools)
            try:
                projection = project_shell_input(
                    current_buffer=session.stdin_buffer,
                    chars=input_payload.chars,
                    keys=input_payload.normalized_keys,
                )
                for line in projection.complete_lines:
                    enforce_shell_policy(
                        line,
                        blacklist=blacklist,
                        tool_name="shell_write_stdin",
                    )
            except MCPToolError:
                await close_shell_session_resources(
                    cleanup_deps,
                    operation=OPERATION_MCP_TOOLS_WRITESTDIN_BLACKLIST_CLEANUP,
                    shell_session_id=session.session_id,
                    terminal_session_id=session.terminal_session_id,
                )
                raise
            try:
                if cols is not None and rows is not None:
                    await utility_tools.terminal.resize_pty(
                        session.terminal_session_id,
                        cols,
                        rows,
                    )
                if input_payload.chars:
                    await utility_tools.terminal.write_pty_input(
                        session.terminal_session_id,
                        input_payload.chars.encode("utf-8", errors="replace"),
                    )
                for payload in input_payload.encoded_keys:
                    await utility_tools.terminal.write_pty_input(
                        session.terminal_session_id,
                        payload,
                    )
            except asyncio.CancelledError:
                await uncancel_then_cleanup(
                    close_shell_session_resources(
                        cleanup_deps,
                        operation=OPERATION_MCP_TOOLS_WRITESTDIN_CLOSE_CLEANUP,
                        shell_session_id=session.session_id,
                        terminal_session_id=session.terminal_session_id,
                    )
                )
                raise
            except HANDLED_RUNTIME_EXCEPTIONS:
                await close_shell_session_resources(
                    cleanup_deps,
                    operation=OPERATION_MCP_TOOLS_WRITESTDIN_CLOSE_CLEANUP,
                    shell_session_id=session.session_id,
                    terminal_session_id=session.terminal_session_id,
                )
                raise
            session.stdin_buffer = projection.tail
    if exited_while_waiting is not None:
        return await complete_exited_shell_write_stdin_session(
            utility_tools,
            cleanup_deps,
            session=session,
            yield_time_ms=yield_time_ms,
            max_output_chars=max_output_chars,
            output_limit=output_limit,
            exit_code=int(exited_while_waiting),
            operation=OPERATION_MCP_TOOLS_WRITESTDIN_CLOSE_CLEANUP,
        )
    drain_result = await drain_shell_write_stdin_output(
        utility_tools,
        session_id=session_id,
        yield_time_ms=yield_time_ms,
        max_output_chars=max_output_chars,
    )
    session_after = utility_tools.runtime_sessions.get_shell_session(session_id)
    exit_code_value = drain_result.exit_code
    if exit_code_value is None and session_after is not None:
        exit_code_value = session_after.exit_code
    if exit_code_value is not None:
        if session.background_watch_started:
            return build_shell_incremental_output_payload(
                utility_tools.runtime_sessions,
                session_id=session_id,
                limit=output_limit,
                exit_code=int(exit_code_value),
                status=None,
            )
        return await complete_closed_shell_write_stdin_session(
            cleanup_deps,
            session=session,
            output_limit=output_limit,
            exit_code=int(exit_code_value),
            operation=OPERATION_MCP_TOOLS_WRITESTDIN_CLOSE_CLEANUP,
        )
    return build_shell_incremental_output_payload(
        utility_tools.runtime_sessions,
        session_id=session_id,
        limit=output_limit,
        exit_code=None,
        status=None,
    )
