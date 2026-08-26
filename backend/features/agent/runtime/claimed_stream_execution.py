"""SoAI - Shared claimed stream execution cleanup [backend/features/agent/runtime/claimed_stream_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.runtime.request_context import RequestContext
from core.runtime.shutdown_errors import (
    build_shutdown_task_cancelled_error,
    is_shutdown_service_unavailable,
)
from features.agent.runtime.turn_finalization import cancel_active_subagent_turns
from features.agent.runtime.turn_lifecycle.claim import claim_agent_turn_for_execution
from features.agent.runtime.turn_lifecycle.finalize import (
    finalize_running_turn_noncritical,
)
from features.agent.runtime.turn_lifecycle.noncritical_finalization_request import (
    build_cancelled_turn_noncritical_finalization_request,
)
from features.agent.runtime.turn_todo_state import parse_agent_todo_state_payload

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.agent.runtime.turn_engine import AgentTurnEngineDependencies

__all__ = ("execute_claimed_stream",)


async def _cancel_root_subagents_before_terminal_turn(
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    conv_id: str,
    user_id: int,
) -> None:
    if context.agent_turn_scope == TURN_SCOPE_SUBAGENT or not context.agent_turn_id:
        return
    await uncancel_then_cleanup(
        cancel_active_subagent_turns(
            database_agent_turns=deps.database_agent_turns,
            task_registry=deps.task_registry,
            conv_id=conv_id,
            user_id=user_id,
            parent_turn_id=context.agent_turn_id,
        ),
    )


async def _finalize_claimed_turn_cancelled(
    *,
    deps: AgentTurnEngineDependencies,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    context: RequestContext,
    conv_id: str,
    user_id: int,
    operation: str,
    cancelled_log_message: str,
) -> None:
    await _cancel_root_subagents_before_terminal_turn(
        deps=deps,
        context=context,
        conv_id=conv_id,
        user_id=user_id,
    )
    await uncancel_then_cleanup(
        finalize_running_turn_noncritical(
            database_agent_turns=database_agent_turns,
            logger=deps.logger,
            request=build_cancelled_turn_noncritical_finalization_request(
                trace_id=context.trace_id,
                conv_id=conv_id,
                user_id=user_id,
                turn_id=context.agent_turn_id,
                execution_token=context.agent_turn_execution_token,
                operation=operation,
                log_message=cancelled_log_message,
            ),
        ),
    )


async def execute_claimed_stream(
    *,
    deps: AgentTurnEngineDependencies,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    context: RequestContext,
    tool_context: MCPToolContext,
    settings: AgentSettings,
    requested_model: str | None,
    todo_state: JSONDict | None,
    conv_id: str,
    user_id: int,
    initial_active_inference_cancellation_id: str | None,
    execute_stream: Callable[[], Awaitable[None]],
    on_claimed: Callable[[], Awaitable[None] | None] | None,
    shutdown_event: asyncio.Event | None,
    operation: str,
    cancelled_log_message: str,
) -> None:
    claimed_turn = False
    try:
        await claim_agent_turn_for_execution(
            deps=deps,
            context=context,
            tool_context=tool_context,
            settings=settings,
            requested_model=requested_model,
            todo_state=parse_agent_todo_state_payload(todo_state),
            initial_active_inference_cancellation_id=initial_active_inference_cancellation_id,
        )
        claimed_turn = True
        if on_claimed is not None:
            claimed_awaitable = on_claimed()
            if claimed_awaitable is not None:
                await claimed_awaitable
        await execute_stream()
    except asyncio.CancelledError:
        if claimed_turn:
            await _finalize_claimed_turn_cancelled(
                deps=deps,
                database_agent_turns=database_agent_turns,
                context=context,
                conv_id=conv_id,
                user_id=user_id,
                operation=operation,
                cancelled_log_message=cancelled_log_message,
            )
        raise
    except TaskCancelledError:
        if claimed_turn:
            await _finalize_claimed_turn_cancelled(
                deps=deps,
                database_agent_turns=database_agent_turns,
                context=context,
                conv_id=conv_id,
                user_id=user_id,
                operation=operation,
                cancelled_log_message=cancelled_log_message,
            )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        if not is_shutdown_service_unavailable(coerced, shutdown_event):
            raise
        if claimed_turn:
            await _finalize_claimed_turn_cancelled(
                deps=deps,
                database_agent_turns=database_agent_turns,
                context=context,
                conv_id=conv_id,
                user_id=user_id,
                operation=operation,
                cancelled_log_message=cancelled_log_message,
            )
        raise build_shutdown_task_cancelled_error(
            initial_active_inference_cancellation_id or context.cancellation_id,
        ) from exception
