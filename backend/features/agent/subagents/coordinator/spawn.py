"""SoAI - Subagent spawn coordinator [backend/features/agent/subagents/coordinator/spawn.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import contextvars
from typing import TYPE_CHECKING

from core.agent.protocols import SubagentAcceptedExecution
from core.agent.status_values import SUBAGENT_STATUS_ACCEPTED
from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.execution.owned_execution_tasks import create_owned_execution_task
from core.runtime.request_context import RequestContext
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from features.agent.subagents.background_parent_stream_setup import (
    maybe_build_parent_update_bridge,
)
from features.agent.subagents.coordinator.spawn_failure_finalization import (
    cleanup_spawn_background_task_noncritical,
    finalize_spawn_failure_noncritical,
)
from features.agent.subagents.parent_state import require_parent_subagent_state
from features.agent.subagents.parent_tool_call_update_models import (
    build_live_subagent_record,
)
from features.agent.subagents.snapshots import build_subagent_snapshot
from features.agent.subagents.spawning import claim_subagent_spawn, plan_subagent_spawn
from features.agent.subagents.subagent_lifecycle_event_publication import (
    publish_subagent_spawned_event,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.tool_calls.current_tool_call import CurrentToolCallIdentity
    from core.types.json import JSONDict
    from features.agent.subagents.internal_protocols import (
        SubagentBackgroundExecutorProtocol,
    )
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "build_spawn_task_metadata",
    "spawn_subagent_execution",
)

OPERATION_SPAWN_SUBAGENT = "agent.subagents.spawn_subagent"
OPERATION_SPAWN_SUBAGENT_CANCELLED_BACKGROUND_TASK = (
    "agent.subagents.spawn_subagent.cancelled.background_task"
)
OPERATION_SPAWN_SUBAGENT_BACKGROUND_TASK = "agent.subagents.spawn_subagent.background_task"


def build_spawn_task_metadata(
    *,
    subagent_id: str,
    parent_turn_id: str,
    tool_call_identity: CurrentToolCallIdentity,
) -> JSONDict:
    return {
        "agentic": True,
        "turn_scope": TURN_SCOPE_SUBAGENT,
        "agent_turn_id": subagent_id,
        "parent_turn_id": parent_turn_id,
        "parent_tool_call_id": tool_call_identity.call_id,
    }


async def spawn_subagent_execution(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
    background_executor: SubagentBackgroundExecutorProtocol,
    active_request_context: contextvars.ContextVar[RequestContext | None],
    active_tool_call_context: contextvars.ContextVar[CurrentToolCallIdentity | None],
    task: str,
    context: str | None,
    mode: str | None,
    display_name: str | None,
    model: str | None,
    workspace_path: str | None,
    max_iterations: int | None,
    tools: tuple[str, ...] | None,
) -> SubagentAcceptedExecution:
    parent_context, tool_call_identity, parent_tool_context = require_parent_subagent_state(
        active_request_context,
        active_tool_call_context,
    )
    spawn_plan = await plan_subagent_spawn(
        api_dependencies=api_dependencies,
        parent_context=parent_context,
        parent_tool_context=parent_tool_context,
        mode=mode,
        model=model,
        workspace_path=workspace_path,
        max_iterations=max_iterations,
        tools=tools,
    )
    coordinator_task = await create_owned_execution_task(
        api_dependencies.task_registry,
        user_id=parent_tool_context.user_id,
        owner_id=parent_tool_context.conv_id,
        owner_type="conversation",
        cancellation_id=spawn_plan.subagent_turn_cancellation_id,
        owner_task_id=None,
        initial_status="queued",
        status_message="Accepted",
        metadata=build_spawn_task_metadata(
            subagent_id=spawn_plan.subagent_id,
            parent_turn_id=parent_context.agent_turn_id or "",
            tool_call_identity=tool_call_identity,
        ),
    )
    subagent_context: RequestContext | None = None
    subagent_tool_context: MCPToolContext | None = None
    parent_tool_call_update_bridge = None
    background_task: asyncio.Task[None] | None = None
    try:
        claimed_spawn = await claim_subagent_spawn(
            api_dependencies=api_dependencies,
            logger=logger,
            parent_context=parent_context,
            parent_tool_context=parent_tool_context,
            tool_call_identity=tool_call_identity,
            spawn_plan=spawn_plan,
            coordinator_task_id=coordinator_task.task_id,
            display_name=display_name,
        )
        subagent_context = claimed_spawn.context
        subagent_tool_context = spawn_plan.subagent_tool_context
        snapshot = build_subagent_snapshot(claimed_spawn.turn_record)
        if snapshot is None:
            raise StateError("Claimed subagent turn snapshot is invalid.")
        await publish_subagent_spawned_event(
            event_bus=api_dependencies.event_bus,
            logger=logger,
            parent_tool_context=parent_tool_context,
            snapshot=snapshot,
        )
        parent_tool_call_update_bridge = maybe_build_parent_update_bridge(
            api_dependencies=api_dependencies,
            logger=logger,
            subagent_context=subagent_context,
            subagent_tool_context=subagent_tool_context,
        )
        if parent_tool_call_update_bridge is not None:
            await parent_tool_call_update_bridge.publish_initial_subagent_state_noncritical(
                subagent_record=build_live_subagent_record(
                    snapshot=snapshot,
                    result_text=snapshot.result_text,
                    token_usage=None,
                ),
            )
        background_task = spawn_tracked_task(
            background_executor.execute(
                subagent_context=subagent_context,
                subagent_tool_context=subagent_tool_context,
                requested_model=spawn_plan.requested_model,
                settings=spawn_plan.settings,
                execution_request=spawn_plan.execution_request,
                coordinator_task_id=coordinator_task.task_id,
                task_text=task,
                task_context=context,
            ),
            name=f"subagent-{spawn_plan.subagent_id}",
            logger=logger,
            cancellation_binder=api_dependencies.task_cancellation_binder,
            cancellation_id=spawn_plan.subagent_turn_cancellation_id,
            owner="agent.subagent",
            metadata={
                "conv_id": parent_tool_context.conv_id,
                "turn_id": spawn_plan.subagent_id,
            },
            finalizer_tracker=api_dependencies.task_finalizer_tracker,
        )
        api_dependencies.application_control.track_background_task(background_task)
    except asyncio.CancelledError:
        await cleanup_spawn_background_task_noncritical(
            logger=logger,
            trace_id=parent_context.trace_id,
            conv_id=parent_tool_context.conv_id,
            coordinator_task_id=coordinator_task.task_id,
            background_task=background_task,
        )
        await finalize_spawn_failure_noncritical(
            api_dependencies=api_dependencies,
            logger=logger,
            parent_context=parent_context,
            parent_tool_context=parent_tool_context,
            subagent_context=subagent_context,
            subagent_tool_context=subagent_tool_context,
            parent_tool_call_update_bridge=parent_tool_call_update_bridge,
            coordinator_task_id=coordinator_task.task_id,
            cancelled=True,
            turn_operation=OPERATION_SPAWN_SUBAGENT_CANCELLED_BACKGROUND_TASK,
            turn_log_message="Failed to finalize subagent turn after background-task cancellation (non-critical).",
            active_inference_reason="Cancelled by parent agent.",
            active_inference_operation=OPERATION_SPAWN_SUBAGENT_CANCELLED_BACKGROUND_TASK,
            active_inference_log_message="Failed to cancel subagent active inference scope (non-critical).",
        )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_SPAWN_SUBAGENT,
        )
        log_exception(
            logger,
            coerced,
            message="Subagent spawn failed before background execution stabilized.",
            trace_id=parent_context.trace_id,
            operation=OPERATION_SPAWN_SUBAGENT,
            details={
                "conv_id": parent_tool_context.conv_id,
                "parent_turn_id": parent_context.agent_turn_id,
                "coordinator_task_id": coordinator_task.task_id,
            },
        )
        await cleanup_spawn_background_task_noncritical(
            logger=logger,
            trace_id=parent_context.trace_id,
            conv_id=parent_tool_context.conv_id,
            coordinator_task_id=coordinator_task.task_id,
            background_task=background_task,
        )
        await finalize_spawn_failure_noncritical(
            api_dependencies=api_dependencies,
            logger=logger,
            parent_context=parent_context,
            parent_tool_context=parent_tool_context,
            subagent_context=subagent_context,
            subagent_tool_context=subagent_tool_context,
            parent_tool_call_update_bridge=parent_tool_call_update_bridge,
            coordinator_task_id=coordinator_task.task_id,
            cancelled=False,
            turn_operation=OPERATION_SPAWN_SUBAGENT_BACKGROUND_TASK,
            turn_log_message="Failed to finalize subagent turn after background-task failure (non-critical).",
            active_inference_reason="Subagent spawn failed.",
            active_inference_operation=OPERATION_SPAWN_SUBAGENT_BACKGROUND_TASK,
            active_inference_log_message="Failed to cancel subagent active inference scope (non-critical).",
        )
        raise
    return SubagentAcceptedExecution(
        subagent_id=spawn_plan.subagent_id,
        owner_task_id=coordinator_task.task_id,
        status=SUBAGENT_STATUS_ACCEPTED,
        mode=spawn_plan.subagent_mode,
        conv_id=parent_tool_context.conv_id,
        requested_model=spawn_plan.requested_model,
    )
