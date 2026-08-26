"""SoAI - Interactive shell write completion [backend/mcp/tools/shell_write_stdin_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.shell_output_payloads import build_shell_incremental_output_payload
from mcp.tools.shell_session_cleanup import require_shell_terminal_session_finalized
from mcp.tools.shell_session_output_streaming import (
    ShellSessionOutputDrainResult,
    drain_shell_session_output_for_interval,
)

if TYPE_CHECKING:
    from core.mcp.runtime_types import ShellSession
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
    from mcp.tools.shell_session_cleanup import ShellSessionCleanupDeps

__all__ = (
    "complete_closed_shell_write_stdin_session",
    "complete_exited_shell_write_stdin_session",
    "drain_shell_write_stdin_output",
)


async def complete_closed_shell_write_stdin_session(
    cleanup_deps: ShellSessionCleanupDeps,
    *,
    session: ShellSession,
    output_limit: int,
    exit_code: int,
    operation: str,
) -> JSONDict:
    await require_shell_terminal_session_finalized(
        cleanup_deps,
        operation=operation,
        shell_session_id=session.session_id,
        terminal_session_id=session.terminal_session_id,
        session=session,
    )
    return build_shell_incremental_output_payload(
        cleanup_deps.runtime_sessions,
        session_id=session.session_id,
        limit=output_limit,
        exit_code=exit_code,
        status=None,
    )


async def drain_shell_write_stdin_output(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    session_id: int,
    yield_time_ms: int,
    max_output_chars: int,
) -> ShellSessionOutputDrainResult:
    return await drain_shell_session_output_for_interval(
        runtime_sessions=utility_tools.runtime_sessions,
        event_bus=utility_tools.event_bus,
        identity=utility_tools.active_tool_call_context.get(None),
        tool_name="shell_write_stdin",
        shell_session_id=session_id,
        wait_ms=yield_time_ms,
        max_return_chars=max_output_chars,
    )


async def complete_exited_shell_write_stdin_session(
    utility_tools: MCPUtilityToolsProtocol,
    cleanup_deps: ShellSessionCleanupDeps,
    *,
    session: ShellSession,
    yield_time_ms: int,
    max_output_chars: int,
    output_limit: int,
    exit_code: int,
    operation: str,
) -> JSONDict:
    await drain_shell_write_stdin_output(
        utility_tools,
        session_id=session.session_id,
        yield_time_ms=yield_time_ms,
        max_output_chars=max_output_chars,
    )
    if session.background_watch_started:
        return build_shell_incremental_output_payload(
            utility_tools.runtime_sessions,
            session_id=session.session_id,
            limit=output_limit,
            exit_code=exit_code,
            status=None,
        )
    return await complete_closed_shell_write_stdin_session(
        cleanup_deps,
        session=session,
        output_limit=output_limit,
        exit_code=exit_code,
        operation=operation,
    )
