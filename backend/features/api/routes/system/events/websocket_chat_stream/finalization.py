"""SoAI - WebSocket chat stream finalization policy [backend/features/api/routes/system/events/websocket_chat_stream/finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.runtime.request_context import RequestContext
from features.agent.runtime.turn_finalization import cancel_active_subagent_turns
from features.agent.runtime.turn_lifecycle.finalize import (
    finalize_running_turn_noncritical,
)
from features.agent.runtime.turn_lifecycle.noncritical_finalization_request import (
    build_cancelled_turn_noncritical_finalization_request,
    build_terminal_turn_noncritical_finalization_request,
)
from features.assistant_timeline.assistant_timeline_shutdown import (
    stop_timeline_session_tickers,
)
from features.assistant_timeline.assistant_timeline_terminal import (
    finalize_assistant_timeline_cancelled,
    finalize_assistant_timeline_error,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )

__all__ = (
    "finalize_ws_chat_stream_cancellation_noncritical",
    "finalize_ws_chat_stream_error_noncritical",
)


async def _cancel_claimed_agent_subagents(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    task_registry: TaskRegistryProtocol,
    runtime_conv_id: str,
    runtime_user_id: int,
    runtime_agent_turn_id: str,
) -> None:
    await uncancel_then_cleanup(
        cancel_active_subagent_turns(
            database_agent_turns=database_agent_turns,
            task_registry=task_registry,
            conv_id=runtime_conv_id,
            user_id=runtime_user_id,
            parent_turn_id=runtime_agent_turn_id,
        ),
    )


async def finalize_ws_chat_stream_cancellation_noncritical(
    *,
    session: AssistantTimelineSession,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    task_registry: TaskRegistryProtocol,
    logger: LoggerProtocol,
    context: RequestContext,
    tool_context: MCPToolContext | None,
) -> None:
    runtime = session.runtime
    if not runtime.terminal_event_emitted and not runtime.terminal_finalization_started:
        if not runtime.cancellation_requested:
            runtime.cancellation_requested = True
        if runtime.cancellation_reason is None:
            runtime.cancellation_reason = "WebSocket chat stream was cancelled."
    await uncancel_then_cleanup(stop_timeline_session_tickers(session))
    if not runtime.terminal_event_emitted and not runtime.terminal_finalization_started:
        await uncancel_then_cleanup(
            finalize_assistant_timeline_cancelled(
                session,
                runtime.cancellation_reason or "Chat stream was cancelled.",
            ),
        )
    if tool_context is None:
        return
    if not runtime.agent_turn_id or not runtime.agent_turn_execution_token:
        return
    await _cancel_claimed_agent_subagents(
        database_agent_turns=database_agent_turns,
        task_registry=task_registry,
        runtime_conv_id=runtime.conv_id,
        runtime_user_id=runtime.user_id,
        runtime_agent_turn_id=runtime.agent_turn_id,
    )
    await uncancel_then_cleanup(
        finalize_running_turn_noncritical(
            database_agent_turns=database_agent_turns,
            logger=logger,
            request=build_cancelled_turn_noncritical_finalization_request(
                trace_id=str(context.trace_id or ""),
                conv_id=runtime.conv_id,
                user_id=runtime.user_id,
                turn_id=runtime.agent_turn_id,
                execution_token=runtime.agent_turn_execution_token,
                operation="webui_ws_chat_stream.finalize_agent_turn_after_cancellation",
                log_message="Failed to finalize claimed agent turn after WebSocket chat stream cancellation (non-critical).",
            ),
        ),
    )


async def finalize_ws_chat_stream_error_noncritical(
    *,
    session: AssistantTimelineSession,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    task_registry: TaskRegistryProtocol,
    logger: LoggerProtocol,
    context: RequestContext,
    tool_context: MCPToolContext | None,
    error_message: str,
    error_code: str,
    turn_error_message: str,
    turn_error_type: str,
) -> None:
    runtime = session.runtime
    if not runtime.terminal_event_emitted and not runtime.terminal_finalization_started:
        await uncancel_then_cleanup(stop_timeline_session_tickers(session))
    if not runtime.terminal_event_emitted and not runtime.terminal_finalization_started:
        await uncancel_then_cleanup(
            finalize_assistant_timeline_error(
                session,
                message=error_message,
                code=error_code,
            ),
        )
    if tool_context is None:
        return
    if not runtime.agent_turn_id or not runtime.agent_turn_execution_token:
        return
    await _cancel_claimed_agent_subagents(
        database_agent_turns=database_agent_turns,
        task_registry=task_registry,
        runtime_conv_id=runtime.conv_id,
        runtime_user_id=runtime.user_id,
        runtime_agent_turn_id=runtime.agent_turn_id,
    )
    await uncancel_then_cleanup(
        finalize_running_turn_noncritical(
            database_agent_turns=database_agent_turns,
            logger=logger,
            request=build_terminal_turn_noncritical_finalization_request(
                trace_id=str(context.trace_id or ""),
                conv_id=runtime.conv_id,
                user_id=runtime.user_id,
                turn_id=runtime.agent_turn_id,
                execution_token=runtime.agent_turn_execution_token,
                status="error",
                reached_max_iterations=False,
                error_message=turn_error_message,
                error_type=turn_error_type,
                operation="webui_ws_chat_stream.finalize_agent_turn_after_error",
                log_message="Failed to finalize claimed agent turn after WebSocket chat stream error (non-critical).",
            ),
        ),
    )
