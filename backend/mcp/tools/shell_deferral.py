"""SoAI - Shell background deferral handoff [backend/mcp/tools/shell_deferral.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.deferred_tool_call_signal import mark_result_deferred
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("maybe_defer_background_shell",)


async def maybe_defer_background_shell(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    tty: bool,
    run_in_background: bool,
    shell_session_id: int,
    terminal_session_id: str,
    max_output_chars: int,
    output_limit: int,
    accepted_result: JSONDict,
) -> JSONDict | None:
    if not (tty or run_in_background):
        return None
    service = utility_tools.shell_background_service
    identity = utility_tools.active_tool_call_context.get(None)
    if service is None or identity is None:
        return None
    if identity.turn_id is None or identity.iteration_index is None:
        return None
    request_context = utility_tools.active_request_context.get(None)
    trace_id = request_context.trace_id if request_context is not None else ""
    start_result = await service.start_background_shell_watch(
        runtime_sessions=utility_tools.runtime_sessions,
        terminal=utility_tools.terminal,
        identity=identity,
        shell_session_id=shell_session_id,
        terminal_session_id=terminal_session_id,
        tty=tty,
        max_output_chars=max_output_chars,
        output_limit=output_limit,
        trace_id=trace_id,
        accepted_result=accepted_result,
    )
    session = utility_tools.runtime_sessions.get_shell_session(shell_session_id)
    if session is not None:
        session.background_watch_started = True
    owner_task_id = str(start_result.get("owner_task_id") or "").strip()
    return mark_result_deferred(
        accepted_result,
        owner_task_id=owner_task_id,
        accepted_state_persisted=True,
    )
