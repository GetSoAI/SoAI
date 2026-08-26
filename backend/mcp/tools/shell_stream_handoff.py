"""SoAI - Bounded streamed shell handoff [backend/mcp/tools/shell_stream_handoff.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from mcp.tools.shell_deferral import maybe_defer_background_shell
from mcp.tools.shell_output_payloads import build_shell_incremental_output_payload
from mcp.tools.shell_session_cleanup import (
    ShellSessionCleanupDeps,
    close_shell_session_resources,
    require_shell_terminal_session_finalized,
)
from mcp.tools.shell_session_output_streaming import (
    drain_shell_session_output_for_interval,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.terminal.protocols import TerminalServiceProtocol
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import (
        MCPToolRuntimeSessionStoreProtocol,
        MCPUtilityToolsProtocol,
    )

__all__ = ("complete_or_defer_streamed_shell",)

OPERATION_STREAMED_SHELL_CLEANUP = "mcp.tools.shell_stream_handoff.cleanup"
OPERATION_STREAMED_SHELL_CANCELLED = "mcp.tools.shell_stream_handoff.cancelled"


async def _close_streamed_shell_resources(
    *,
    runtime_sessions: MCPToolRuntimeSessionStoreProtocol,
    terminal: TerminalServiceProtocol,
    logger: LoggerProtocol,
    shell_session_id: int,
    terminal_session_id: str,
    operation: str,
) -> None:
    await close_shell_session_resources(
        ShellSessionCleanupDeps(
            runtime_sessions=runtime_sessions,
            terminal=terminal,
            logger=logger,
        ),
        operation=operation,
        shell_session_id=shell_session_id,
        terminal_session_id=terminal_session_id,
    )


async def complete_or_defer_streamed_shell(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    logger: LoggerProtocol,
    tty: bool,
    shell_session_id: int,
    terminal_session_id: str,
    max_output_chars: int,
    output_limit: int,
    yield_time_ms: int,
) -> JSONDict:
    try:
        drain_result = await drain_shell_session_output_for_interval(
            runtime_sessions=utility_tools.runtime_sessions,
            event_bus=utility_tools.event_bus,
            identity=utility_tools.active_tool_call_context.get(None),
            tool_name="shell",
            shell_session_id=shell_session_id,
            wait_ms=yield_time_ms,
            max_return_chars=max_output_chars,
        )
        if drain_result.exit_code is not None:
            await require_shell_terminal_session_finalized(
                ShellSessionCleanupDeps(
                    runtime_sessions=utility_tools.runtime_sessions,
                    terminal=utility_tools.terminal,
                    logger=logger,
                ),
                operation=OPERATION_STREAMED_SHELL_CLEANUP,
                shell_session_id=shell_session_id,
                terminal_session_id=terminal_session_id,
            )
            return build_shell_incremental_output_payload(
                utility_tools.runtime_sessions,
                session_id=shell_session_id,
                limit=output_limit,
                exit_code=int(drain_result.exit_code),
                status=None,
            )
        session = utility_tools.runtime_sessions.get_shell_session(shell_session_id)
        if session is None:
            raise StateError("Streamed shell session disappeared before completion.")
        session.run_in_background = True
        running_result = build_shell_incremental_output_payload(
            utility_tools.runtime_sessions,
            session_id=shell_session_id,
            limit=output_limit,
            exit_code=None,
            status="running",
        )
        deferred_result = await maybe_defer_background_shell(
            utility_tools,
            tty=tty,
            run_in_background=True,
            shell_session_id=shell_session_id,
            terminal_session_id=terminal_session_id,
            max_output_chars=max_output_chars,
            output_limit=output_limit,
            accepted_result=running_result,
        )
        if deferred_result is not None:
            return deferred_result
        return running_result
    except asyncio.CancelledError:
        await uncancel_then_cleanup(
            _close_streamed_shell_resources(
                runtime_sessions=utility_tools.runtime_sessions,
                terminal=utility_tools.terminal,
                logger=logger,
                shell_session_id=shell_session_id,
                terminal_session_id=terminal_session_id,
                operation=OPERATION_STREAMED_SHELL_CANCELLED,
            ),
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS:
        await _close_streamed_shell_resources(
            runtime_sessions=utility_tools.runtime_sessions,
            terminal=utility_tools.terminal,
            logger=logger,
            shell_session_id=shell_session_id,
            terminal_session_id=terminal_session_id,
            operation=OPERATION_STREAMED_SHELL_CLEANUP,
        )
        raise
