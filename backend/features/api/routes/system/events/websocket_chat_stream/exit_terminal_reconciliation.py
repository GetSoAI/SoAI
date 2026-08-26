"""SoAI - WebSocket chat stream exit terminal reconciliation [backend/features/api/routes/system/events/websocket_chat_stream/exit_terminal_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from features.api.routes.system.events.websocket_chat_stream.finalization import (
    finalize_ws_chat_stream_cancellation_noncritical,
    finalize_ws_chat_stream_error_noncritical,
)
from features.api.routes.system.events.websocket_chat_stream.terminal_state import (
    resolve_ws_chat_stream_terminal_turn_state,
)
from features.assistant_timeline.agentic_outcome import resolve_agentic_terminal_outcome
from features.assistant_timeline.assistant_timeline_terminal import (
    finalize_agentic_stream_timeline,
    finalize_assistant_timeline_non_agentic,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )

__all__ = ("reconcile_unterminated_ws_chat_stream_exit",)

OPERATION = "api_system.ws_chat_stream.exit_terminal_reconciliation"
UNTERMINATED_EXIT_MESSAGE = "WebSocket chat stream exited without terminal assistant finalization."


async def _reconcile_non_agent_exit(
    *,
    session: AssistantTimelineSession,
    task_registry: TaskRegistryProtocol,
    api_context: ApiContext,
    logger: LoggerProtocol,
    context: RequestContext,
) -> None:
    active_task_id = session.runtime.active_task_id
    if active_task_id is not None and active_task_id:
        task = await task_registry.get(active_task_id, force_refresh=True)
        if task is not None:
            await finalize_assistant_timeline_non_agentic(
                session,
                task=task,
                task_lookup=lambda task_id: task_registry.get(task_id, force_refresh=True),
            )
            return
    if session.runtime.cancellation_requested:
        await finalize_ws_chat_stream_cancellation_noncritical(
            session=session,
            database_agent_turns=api_context.dependencies.database_agent_turns,
            task_registry=task_registry,
            logger=logger,
            context=context,
            tool_context=None,
        )
        return
    await finalize_ws_chat_stream_error_noncritical(
        session=session,
        database_agent_turns=api_context.dependencies.database_agent_turns,
        task_registry=task_registry,
        logger=logger,
        context=context,
        tool_context=None,
        error_message=UNTERMINATED_EXIT_MESSAGE,
        error_code="server_error",
        turn_error_message=UNTERMINATED_EXIT_MESSAGE,
        turn_error_type="server_error",
    )


async def _reconcile_agent_exit(
    *,
    session: AssistantTimelineSession,
    task_registry: TaskRegistryProtocol,
    api_context: ApiContext,
    logger: LoggerProtocol,
    context: RequestContext,
    tool_context: MCPToolContext,
) -> None:
    if session.runtime.cancellation_requested:
        await finalize_ws_chat_stream_cancellation_noncritical(
            session=session,
            database_agent_turns=api_context.dependencies.database_agent_turns,
            task_registry=task_registry,
            logger=logger,
            context=context,
            tool_context=tool_context,
        )
        return
    turn_state = await resolve_ws_chat_stream_terminal_turn_state(
        api_context=api_context,
        runtime=session.runtime,
        logger=logger,
        trace_id=context.trace_id,
    )

    async def resolved_turn_state_loader() -> JSONDict | None:
        return turn_state

    await finalize_agentic_stream_timeline(
        session,
        turn_state_loader=resolved_turn_state_loader,
        resolve_terminal_outcome=resolve_agentic_terminal_outcome,
    )


async def reconcile_unterminated_ws_chat_stream_exit(
    *,
    session: AssistantTimelineSession,
    task_registry: TaskRegistryProtocol,
    api_context: ApiContext,
    logger: LoggerProtocol,
    context: RequestContext,
    tool_context: MCPToolContext | None,
) -> None:
    runtime = session.runtime
    if runtime.terminal_persistence_completed:
        return
    try:
        if tool_context is None:
            await _reconcile_non_agent_exit(
                session=session,
                task_registry=task_registry,
                api_context=api_context,
                logger=logger,
                context=context,
            )
            return
        await _reconcile_agent_exit(
            session=session,
            task_registry=task_registry,
            api_context=api_context,
            logger=logger,
            context=context,
            tool_context=tool_context,
        )
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            logger,
            coerce_to_soai_error(exception, operation=OPERATION),
            operation=OPERATION,
            message="Failed to reconcile unterminated WebSocket chat stream exit.",
            trace_id=context.trace_id,
            details={
                "conv_id": runtime.conv_id,
                "request_id": runtime.request_id,
                "user_id": runtime.user_id,
            },
        )
