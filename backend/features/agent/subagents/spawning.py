"""SoAI - Subagent spawn planning and turn claim [backend/features/agent/subagents/spawning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.agent.turn_state_requests import require_turn_execution_token
from core.errors.exceptions import ValidationError
from core.logging.protocols import LoggerProtocol
from core.orchestrator.types import MCPToolContext
from core.runtime.cancellation_ids import (
    build_agent_turn_cancellation_id,
    build_subagent_base_cancellation_id,
)
from core.runtime.request_context import RequestContext
from core.runtime.request_context_cloning import clone_request_context
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tool_calls.current_tool_call import CurrentToolCallIdentity
from features.agent.runtime.execution_preparation import (
    build_headless_agent_turn_engine_dependencies_from_api_dependencies,
)
from features.agent.runtime.turn_engine import create_turn_id
from features.agent.runtime.turn_lifecycle.transitions import start_or_resume_turn_state
from features.agent.runtime.turn_todo_state import parse_agent_todo_state_payload
from features.agent.subagents.policy import (
    build_subagent_tool_context,
    resolve_subagent_mode,
)
from features.agent.subagents.settings import resolve_subagent_settings

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "ClaimedSubagentSpawn",
    "SubagentSpawnPlan",
    "claim_subagent_spawn",
    "plan_subagent_spawn",
)


@dataclass(frozen=True, slots=True)
class SubagentSpawnPlan:
    subagent_id: str
    subagent_mode: str
    requested_model: str
    settings: AgentSettings
    execution_request: JSONDict
    subagent_tool_context: MCPToolContext
    base_cancellation_id: str
    subagent_turn_cancellation_id: str


@dataclass(frozen=True, slots=True)
class ClaimedSubagentSpawn:
    context: RequestContext
    turn_record: JSONDict


async def plan_subagent_spawn(
    *,
    api_dependencies: ApiDependencies,
    parent_context: RequestContext,
    parent_tool_context: MCPToolContext,
    mode: str | None,
    model: str | None,
    workspace_path: str | None,
    max_iterations: int | None,
    tools: tuple[str, ...] | None,
) -> SubagentSpawnPlan:
    subagent_mode = resolve_subagent_mode(parent_context.agent_mode or "", mode)
    requested_model, settings, execution_request = await resolve_subagent_settings(
        api_dependencies,
        parent_context=parent_context,
        mode=subagent_mode,
        model=model,
        workspace_path=workspace_path,
        max_iterations=max_iterations,
    )
    subagent_tool_context = build_subagent_tool_context(
        parent_tool_context,
        subagent_mode=subagent_mode,
        requested_tools=tools,
    )
    subagent_id = create_turn_id()
    parent_cancellation_id = normalize_cancellation_id(parent_context.cancellation_id)
    if not parent_cancellation_id:
        raise ValidationError("Subagent spawn requires a parent cancellation_id.")
    base_cancellation_id = build_subagent_base_cancellation_id(
        parent_cancellation_id=parent_cancellation_id,
        subagent_id=subagent_id,
    )
    subagent_turn_cancellation_id = build_agent_turn_cancellation_id(
        base_cancellation_id=base_cancellation_id,
        turn_id=subagent_id,
        mode=subagent_mode,
    )
    return SubagentSpawnPlan(
        subagent_id=subagent_id,
        subagent_mode=subagent_mode,
        requested_model=requested_model,
        settings=settings,
        execution_request=execution_request,
        subagent_tool_context=subagent_tool_context,
        base_cancellation_id=base_cancellation_id,
        subagent_turn_cancellation_id=subagent_turn_cancellation_id,
    )


async def claim_subagent_spawn(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
    parent_context: RequestContext,
    parent_tool_context: MCPToolContext,
    tool_call_identity: CurrentToolCallIdentity,
    spawn_plan: SubagentSpawnPlan,
    coordinator_task_id: str,
    display_name: str | None,
) -> ClaimedSubagentSpawn:
    if parent_context.agent_turn_id is None or not parent_context.agent_turn_id.strip():
        raise ValidationError("Subagent spawn requires an active parent turn id.")
    if parent_context.agent_iteration_index is None:
        raise ValidationError("Subagent spawn requires an active parent iteration index.")
    subagent_context = clone_request_context(
        parent_context,
        task_id=coordinator_task_id,
        cancellation_id=spawn_plan.base_cancellation_id,
        agent_mode=spawn_plan.subagent_mode,
        agent_turn_id=spawn_plan.subagent_id,
        agent_turn_scope=TURN_SCOPE_SUBAGENT,
        agent_iteration_index=0,
        agent_parent_turn_id=parent_context.agent_turn_id,
        agent_parent_tool_call_id=tool_call_identity.call_id,
        agent_parent_iteration_index=parent_context.agent_iteration_index,
        agent_display_name=display_name,
        agent_requested_model=spawn_plan.requested_model,
        agent_owner_task_id=coordinator_task_id,
        agent_workspace_path=spawn_plan.settings.workspace_path,
    )
    subagent_deps = build_headless_agent_turn_engine_dependencies_from_api_dependencies(
        api_dependencies=api_dependencies,
        logger=logger,
    )
    claimed_turn = await start_or_resume_turn_state(
        subagent_deps,
        conv_id=parent_tool_context.conv_id,
        user_id=parent_tool_context.user_id,
        turn_id=spawn_plan.subagent_id,
        mode=spawn_plan.subagent_mode,
        max_iterations=spawn_plan.settings.max_iterations,
        turn_cancellation_id=spawn_plan.subagent_turn_cancellation_id,
        initial_active_inference_cancellation_id=None,
        todo_state=parse_agent_todo_state_payload(None),
        existing_execution_token=None,
        turn_scope=TURN_SCOPE_SUBAGENT,
        parent_turn_id=parent_context.agent_turn_id,
        parent_tool_call_id=tool_call_identity.call_id,
        parent_iteration_index=parent_context.agent_iteration_index,
        display_name=display_name,
        requested_model=spawn_plan.requested_model,
        owner_task_id=coordinator_task_id,
    )
    subagent_context.agent_turn_execution_token = require_turn_execution_token(
        claimed_turn,
        operation="agent.subagents.claim_subagent_spawn",
    )
    return ClaimedSubagentSpawn(
        context=subagent_context,
        turn_record=claimed_turn,
    )
