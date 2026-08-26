"""SoAI - Subagent spawn failure finalization [backend/features/agent/subagents/coordinator/spawn_failure_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_ERROR,
    SUBAGENT_STATUS_RUNNING,
)
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_logging import log_handled_exception
from core.execution.owned_execution_tasks import finalize_owned_execution_task
from core.runtime.request_context import RequestContext
from core.tasks.enums import TaskStatus
from features.agent.runtime.turn_lifecycle.finalize import (
    finalize_running_turn_noncritical,
)
from features.agent.runtime.turn_lifecycle.noncritical_finalization_request import (
    build_terminal_turn_noncritical_finalization_request,
)
from features.agent.subagents.background_finalization_actions import (
    finalize_parent_tool_call_noncritical,
)
from features.agent.subagents.background_parent_stream_setup import (
    maybe_build_parent_update_bridge,
)
from features.agent.subagents.coordinator.cancellation import (
    cancel_subagent_active_inference_scope_noncritical,
)
from features.agent.subagents.subagent_lifecycle_event_publication import (
    publish_subagent_terminal_event,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from features.agent.subagents.parent_tool_call_updates import (
        SubagentParentToolCallUpdateBridge,
    )
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "cleanup_spawn_background_task_noncritical",
    "finalize_spawn_failure_noncritical",
)

OPERATION_SPAWN_SUBAGENT = "agent.subagents.spawn_subagent"


async def cleanup_spawn_background_task_noncritical(
    *,
    logger: LoggerProtocol,
    trace_id: str,
    conv_id: str,
    coordinator_task_id: str,
    background_task: asyncio.Task[None] | None,
) -> None:
    if background_task is None or background_task.done():
        return
    background_task.cancel()
    await uncancel_then_cleanup(cancel_and_await((background_task,)))
    if background_task.cancelled():
        return
    exception = background_task.exception()
    if exception is None:
        return
    log_handled_exception(
        logger,
        exception,
        message="Background subagent execution task raised during cancellation cleanup (non-critical).",
        trace_id=trace_id,
        operation=OPERATION_SPAWN_SUBAGENT,
        details={
            "conv_id": conv_id,
            "coordinator_task_id": coordinator_task_id,
        },
        level="debug",
    )


async def finalize_spawn_failure_noncritical(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
    parent_context: RequestContext,
    parent_tool_context: MCPToolContext,
    subagent_context: RequestContext | None,
    subagent_tool_context: MCPToolContext | None,
    parent_tool_call_update_bridge: SubagentParentToolCallUpdateBridge | None,
    coordinator_task_id: str,
    cancelled: bool,
    turn_operation: str,
    turn_log_message: str,
    active_inference_reason: str,
    active_inference_operation: str,
    active_inference_log_message: str,
) -> None:
    persisted_task = await api_dependencies.task_registry.get(coordinator_task_id)
    if persisted_task is not None and persisted_task.status.is_terminal():
        return
    if subagent_context is not None:
        error_message = "Agent turn cancelled." if cancelled else "Subagent spawn failed."
        error_type = "cancelled" if cancelled else "subagent_spawn_error"
        await finalize_running_turn_noncritical(
            database_agent_turns=api_dependencies.database_agent_turns,
            logger=logger,
            request=build_terminal_turn_noncritical_finalization_request(
                trace_id=parent_context.trace_id,
                conv_id=parent_tool_context.conv_id,
                user_id=parent_tool_context.user_id,
                turn_id=subagent_context.agent_turn_id,
                execution_token=subagent_context.agent_turn_execution_token,
                status=AGENT_TURN_STATUS_CANCELLED if cancelled else AGENT_TURN_STATUS_ERROR,
                reached_max_iterations=False,
                error_message=error_message,
                error_type=error_type,
                operation=turn_operation,
                log_message=turn_log_message,
            ),
        )
    if subagent_context is not None:
        await cancel_subagent_active_inference_scope_noncritical(
            api_dependencies=api_dependencies,
            logger=logger,
            trace_id=parent_context.trace_id,
            conv_id=parent_tool_context.conv_id,
            user_id=parent_tool_context.user_id,
            subagent_id=str(subagent_context.agent_turn_id or ""),
            reason=active_inference_reason,
            operation=active_inference_operation,
            log_message=active_inference_log_message,
        )
        resolved_tool_context = (
            parent_tool_context if subagent_tool_context is None else subagent_tool_context
        )
        resolved_bridge = parent_tool_call_update_bridge
        if resolved_bridge is None:
            resolved_bridge = maybe_build_parent_update_bridge(
                api_dependencies=api_dependencies,
                logger=logger,
                subagent_context=subagent_context,
                subagent_tool_context=resolved_tool_context,
            )
        turn_record = await api_dependencies.database_agent_turns.get_subagent_turn(
            conv_id=resolved_tool_context.conv_id,
            user_id=resolved_tool_context.user_id,
            turn_id=str(subagent_context.agent_turn_id or ""),
        )
        if (
            isinstance(turn_record, dict)
            and str(turn_record.get("status") or "").strip() != SUBAGENT_STATUS_RUNNING
        ):
            await finalize_parent_tool_call_noncritical(
                bridge=resolved_bridge,
                turn_record=turn_record,
                token_usage=None,
            )
            await publish_subagent_terminal_event(
                event_bus=api_dependencies.event_bus,
                logger=logger,
                context=subagent_context,
                turn_record=turn_record,
                token_usage=None,
            )
    await finalize_owned_execution_task(
        api_dependencies.task_registry,
        owner_task_id=coordinator_task_id,
        final_status=(TaskStatus.CANCELLED.value if cancelled else TaskStatus.FAILED.value),
        error_message="Subagent spawn cancelled." if cancelled else "Subagent spawn failed.",
        status_message="Cancelled" if cancelled else "Failed",
    )
