"""SoAI - Request context cloning [backend/core/runtime/request_context_cloning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.runtime.request_context import RequestContext
from core.state.access import AccessAction

if TYPE_CHECKING:
    from core.orchestrator.types import MCPToolContext

__all__ = ("clone_request_context",)


def clone_request_context(
    request_context: RequestContext,
    *,
    task_id: str | None = None,
    mutation_fencing_token: int | None = None,
    cancellation_id: str | None = None,
    mcp_tool_context: MCPToolContext | None = None,
    interactive_tool_approval: bool | None = None,
    agent_mode: str | None = None,
    agent_turn_id: str | None = None,
    agent_turn_scope: str | None = None,
    agent_turn_execution_token: str | None = None,
    agent_iteration_index: int | None = None,
    agent_parent_turn_id: str | None = None,
    agent_parent_tool_call_id: str | None = None,
    agent_parent_iteration_index: int | None = None,
    agent_display_name: str | None = None,
    agent_requested_model: str | None = None,
    agent_owner_task_id: str | None = None,
    agent_workspace_path: str | None = None,
    conversation_input_id: str | None = None,
    conversation_input_claim_generation: int | None = None,
    conversation_input_claim_owner: str | None = None,
    conversation_input_server_boot_id: str | None = None,
    conversation_input_resume_phase: str | None = None,
    conversation_input_resume_task_id: str | None = None,
    conversation_input_resume_tool_call_id: str | None = None,
    conversation_input_resume_generation: int | None = None,
    access_actions: frozenset[AccessAction] | None = None,
) -> RequestContext:
    return RequestContext(
        trace_id=request_context.trace_id,
        client_ip=request_context.client_ip,
        user_id=request_context.user_id,
        timestamp=request_context.timestamp,
        task_id=request_context.task_id if task_id is None else task_id,
        mutation_fencing_token=(
            request_context.mutation_fencing_token
            if mutation_fencing_token is None
            else mutation_fencing_token
        ),
        cancellation_id=(
            request_context.cancellation_id if cancellation_id is None else cancellation_id
        ),
        mcp_tool_context=(
            request_context.mcp_tool_context if mcp_tool_context is None else mcp_tool_context
        ),
        interactive_tool_approval=(
            request_context.interactive_tool_approval
            if interactive_tool_approval is None
            else interactive_tool_approval
        ),
        agent_mode=request_context.agent_mode if agent_mode is None else agent_mode,
        agent_turn_id=(request_context.agent_turn_id if agent_turn_id is None else agent_turn_id),
        agent_turn_scope=(
            request_context.agent_turn_scope if agent_turn_scope is None else agent_turn_scope
        ),
        agent_turn_execution_token=(
            request_context.agent_turn_execution_token
            if agent_turn_execution_token is None
            else agent_turn_execution_token
        ),
        agent_iteration_index=(
            request_context.agent_iteration_index
            if agent_iteration_index is None
            else agent_iteration_index
        ),
        agent_parent_turn_id=(
            request_context.agent_parent_turn_id
            if agent_parent_turn_id is None
            else agent_parent_turn_id
        ),
        agent_parent_tool_call_id=(
            request_context.agent_parent_tool_call_id
            if agent_parent_tool_call_id is None
            else agent_parent_tool_call_id
        ),
        agent_parent_iteration_index=(
            request_context.agent_parent_iteration_index
            if agent_parent_iteration_index is None
            else agent_parent_iteration_index
        ),
        agent_display_name=(
            request_context.agent_display_name if agent_display_name is None else agent_display_name
        ),
        agent_requested_model=(
            request_context.agent_requested_model
            if agent_requested_model is None
            else agent_requested_model
        ),
        agent_owner_task_id=(
            request_context.agent_owner_task_id
            if agent_owner_task_id is None
            else agent_owner_task_id
        ),
        agent_workspace_path=(
            request_context.agent_workspace_path
            if agent_workspace_path is None
            else agent_workspace_path
        ),
        conversation_input_id=(
            request_context.conversation_input_id
            if conversation_input_id is None
            else conversation_input_id
        ),
        conversation_input_claim_generation=(
            request_context.conversation_input_claim_generation
            if conversation_input_claim_generation is None
            else conversation_input_claim_generation
        ),
        conversation_input_claim_owner=(
            request_context.conversation_input_claim_owner
            if conversation_input_claim_owner is None
            else conversation_input_claim_owner
        ),
        conversation_input_server_boot_id=(
            request_context.conversation_input_server_boot_id
            if conversation_input_server_boot_id is None
            else conversation_input_server_boot_id
        ),
        conversation_input_resume_phase=(
            request_context.conversation_input_resume_phase
            if conversation_input_resume_phase is None
            else conversation_input_resume_phase
        ),
        conversation_input_resume_task_id=(
            request_context.conversation_input_resume_task_id
            if conversation_input_resume_task_id is None
            else conversation_input_resume_task_id
        ),
        conversation_input_resume_tool_call_id=(
            request_context.conversation_input_resume_tool_call_id
            if conversation_input_resume_tool_call_id is None
            else conversation_input_resume_tool_call_id
        ),
        conversation_input_resume_generation=(
            request_context.conversation_input_resume_generation
            if conversation_input_resume_generation is None
            else conversation_input_resume_generation
        ),
        access_actions=(
            request_context.access_actions if access_actions is None else access_actions
        ),
    )
