"""SoAI - MCP shell foreground completion handling [backend/mcp/tools/shell_foreground_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from mcp.tools.shell_output_payloads import build_shell_incremental_output_payload
from mcp.tools.shell_session_cleanup import require_shell_terminal_session_finalized

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
    from mcp.tools.runtime_types import ShellSession
    from mcp.tools.shell_session_cleanup import ShellSessionCleanupDeps

__all__ = ("finish_foreground_shell",)


async def finish_foreground_shell(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    cleanup_deps: ShellSessionCleanupDeps,
    shell_session: ShellSession,
    terminal_session_id: str,
    tty: bool,
    yield_time_ms: int,
    output_limit: int,
    operation: str,
) -> JSONDict:
    if yield_time_ms:
        await asyncio.sleep(float(yield_time_ms) / 1000.0)
    session_after = utility_tools.runtime_sessions.get_shell_session(shell_session.session_id)
    exit_code = session_after.exit_code if session_after is not None else None
    if exit_code is not None and not tty:
        await require_shell_terminal_session_finalized(
            cleanup_deps,
            operation=operation,
            shell_session_id=shell_session.session_id,
            terminal_session_id=terminal_session_id,
            session=shell_session,
        )
        return build_shell_incremental_output_payload(
            utility_tools.runtime_sessions,
            session_id=shell_session.session_id,
            limit=output_limit,
            exit_code=exit_code,
            status=None,
        )
    return build_shell_incremental_output_payload(
        utility_tools.runtime_sessions,
        session_id=shell_session.session_id,
        limit=output_limit,
        exit_code=None,
        status="running" if tty else None,
    )
