"""SoAI - MCP shell-session cleanup helpers [backend/mcp/tools/shell_session_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.terminal.protocols import TerminalServiceProtocol
    from core.types.json import JSONValue
    from mcp.tools.internal_protocols import MCPToolRuntimeSessionStoreProtocol
    from mcp.tools.runtime_types import ShellSession

__all__ = (
    "ShellSessionCleanupDeps",
    "build_shell_session_cleanup_details",
    "close_shell_session_resources",
    "finalize_shell_terminal_session",
    "require_shell_terminal_session_finalized",
)


@dataclass(frozen=True, slots=True)
class ShellSessionCleanupDeps:
    runtime_sessions: MCPToolRuntimeSessionStoreProtocol
    terminal: TerminalServiceProtocol
    logger: LoggerProtocol


async def close_shell_session_resources(
    deps: ShellSessionCleanupDeps,
    *,
    operation: str,
    shell_session_id: int,
    terminal_session_id: str,
) -> None:
    finalized = await finalize_shell_terminal_session(
        deps,
        operation=operation,
        shell_session_id=shell_session_id,
        terminal_session_id=terminal_session_id,
    )
    if not finalized:
        deps.runtime_sessions.close_shell_session(shell_session_id)
        raise StateError(
            "Shell terminal cleanup failed and was queued for retry.",
            operation=operation,
            details=build_shell_session_cleanup_details(
                shell_session_id=shell_session_id,
                terminal_session_id=terminal_session_id,
            ),
        )
    deps.runtime_sessions.close_shell_session(shell_session_id)


async def finalize_shell_terminal_session(
    deps: ShellSessionCleanupDeps,
    *,
    operation: str,
    shell_session_id: int,
    terminal_session_id: str,
    session: ShellSession | None = None,
) -> bool:
    target_session = session
    if target_session is None:
        target_session = deps.runtime_sessions.get_shell_session(shell_session_id)
    if target_session is not None and target_session.terminal_session_finalized:
        return True
    try:
        await deps.terminal.close_pty_session(terminal_session_id)
        if target_session is not None:
            target_session.terminal_session_finalized = True
        return True
    except HANDLED_RUNTIME_EXCEPTIONS as cleanup_error:
        details = build_shell_session_cleanup_details(
            shell_session_id=shell_session_id,
            terminal_session_id=terminal_session_id,
        )
        log_exception(
            deps.logger,
            cleanup_error,
            message="Failed to close MCP shell PTY session; cleanup was queued for retry.",
            operation=operation,
            details=details,
            level="warning",
        )
        latest_session = target_session
        if latest_session is None:
            latest_session = deps.runtime_sessions.get_shell_session(shell_session_id)
        if latest_session is not None:
            deps.runtime_sessions.requeue_shell_session_for_terminal_close(latest_session)
        return False


async def require_shell_terminal_session_finalized(
    deps: ShellSessionCleanupDeps,
    *,
    operation: str,
    shell_session_id: int,
    terminal_session_id: str,
    session: ShellSession | None = None,
) -> None:
    finalized = await finalize_shell_terminal_session(
        deps,
        operation=operation,
        shell_session_id=shell_session_id,
        terminal_session_id=terminal_session_id,
        session=session,
    )
    if finalized:
        return
    raise StateError(
        "Shell terminal cleanup failed and was queued for retry.",
        operation=operation,
        details=build_shell_session_cleanup_details(
            shell_session_id=shell_session_id,
            terminal_session_id=terminal_session_id,
        ),
    )


def build_shell_session_cleanup_details(
    *,
    shell_session_id: int,
    terminal_session_id: str,
) -> dict[str, JSONValue]:
    return {
        "session_id": int(shell_session_id),
        "terminal_session_id": terminal_session_id,
    }
