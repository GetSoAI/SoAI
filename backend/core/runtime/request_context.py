"""SoAI - Request context shared across the backend [backend/core/runtime/request_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.runtime.request_context_normalization import (
    normalize_optional_non_negative_int,
    normalize_optional_string,
    normalize_optional_turn_scope,
    normalize_required_cancellation_id,
    resolve_context_identifier_args,
)
from core.runtime.soai_identifiers import create_system_id
from core.state.access import AccessAction
from core.tasks.identifiers import normalize_optional_task_id
from core.timing.epoch import epoch_seconds_float

if TYPE_CHECKING:
    from core.orchestrator.types import MCPToolContext

__all__ = (
    "RequestContext",
    "create_system_context",
)


@dataclass(init=False, slots=True)
class RequestContext:
    trace_id: str
    cancellation_id: str
    client_ip: str | None = None
    user_id: int = 0
    timestamp: float = field(default_factory=epoch_seconds_float)
    task_id: str | None = None
    mutation_fencing_token: int | None = None
    mcp_tool_context: MCPToolContext | None = None
    interactive_tool_approval: bool = False
    agent_mode: str | None = None
    agent_turn_id: str | None = None
    agent_turn_scope: str | None = None
    agent_turn_execution_token: str | None = None
    agent_iteration_index: int | None = None
    agent_parent_turn_id: str | None = None
    agent_parent_tool_call_id: str | None = None
    agent_parent_iteration_index: int | None = None
    agent_display_name: str | None = None
    agent_requested_model: str | None = None
    agent_owner_task_id: str | None = None
    agent_workspace_path: str | None = None
    conversation_input_id: str | None = None
    conversation_input_claim_generation: int | None = None
    conversation_input_claim_owner: str | None = None
    conversation_input_server_boot_id: str | None = None
    conversation_input_resume_phase: str | None = None
    conversation_input_resume_task_id: str | None = None
    conversation_input_resume_tool_call_id: str | None = None
    conversation_input_resume_generation: int | None = None
    access_actions: frozenset[AccessAction] = frozenset()

    def __init__(
        self,
        *args: str | None,
        trace_id: str | None = None,
        client_ip: str | None = None,
        user_id: int = 0,
        timestamp: float | None = None,
        task_id: str | None = None,
        mutation_fencing_token: int | None = None,
        cancellation_id: str | None = None,
        mcp_tool_context: MCPToolContext | None = None,
        interactive_tool_approval: bool = False,
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
    ) -> None:
        task_id_value, trace_id_value, client_ip_value = resolve_context_identifier_args(
            args,
            task_id=task_id,
            trace_id=trace_id,
            client_ip=client_ip,
        )
        if timestamp is None:
            timestamp = epoch_seconds_float()
        if not isinstance(trace_id_value, str) or not trace_id_value:
            raise ValidationError("RequestContext requires trace_id.")
        if task_id_value is not None and not isinstance(task_id_value, str):
            raise ValidationError("RequestContext.task_id must be a string when provided.")
        normalized_task_id = normalize_optional_task_id(task_id_value)
        normalized_mutation_fencing_token = normalize_optional_non_negative_int(
            mutation_fencing_token,
            label="RequestContext.mutation_fencing_token",
        )
        normalized_cancellation_id = normalize_required_cancellation_id(cancellation_id)
        normalized_client_ip = normalize_optional_string(
            client_ip_value,
            label="RequestContext.client_ip",
        )
        if not isinstance(interactive_tool_approval, bool):
            raise ValidationError(
                "RequestContext.interactive_tool_approval must be a boolean when provided.",
            )
        normalized_agent_mode = normalize_optional_string(
            agent_mode,
            label="RequestContext.agent_mode",
        )
        normalized_agent_turn_id = normalize_optional_string(
            agent_turn_id,
            label="RequestContext.agent_turn_id",
        )
        normalized_agent_turn_scope = normalize_optional_turn_scope(agent_turn_scope)
        normalized_agent_turn_execution_token = normalize_optional_string(
            agent_turn_execution_token,
            label="RequestContext.agent_turn_execution_token",
        )
        normalized_agent_iteration_index = normalize_optional_non_negative_int(
            agent_iteration_index,
            label="RequestContext.agent_iteration_index",
        )
        normalized_agent_parent_turn_id = normalize_optional_string(
            agent_parent_turn_id,
            label="RequestContext.agent_parent_turn_id",
        )
        normalized_agent_parent_tool_call_id = normalize_optional_string(
            agent_parent_tool_call_id,
            label="RequestContext.agent_parent_tool_call_id",
        )
        normalized_agent_parent_iteration_index = normalize_optional_non_negative_int(
            agent_parent_iteration_index,
            label="RequestContext.agent_parent_iteration_index",
        )
        normalized_agent_display_name = normalize_optional_string(
            agent_display_name,
            label="RequestContext.agent_display_name",
        )
        normalized_agent_requested_model = normalize_optional_string(
            agent_requested_model,
            label="RequestContext.agent_requested_model",
        )
        if agent_owner_task_id is not None and not isinstance(agent_owner_task_id, str):
            raise ValidationError(
                "RequestContext.agent_owner_task_id must be a string when provided.",
            )
        normalized_agent_owner_task_id = normalize_optional_task_id(agent_owner_task_id)
        normalized_workspace_path = normalize_optional_string(
            agent_workspace_path,
            label="RequestContext.agent_workspace_path",
        )
        normalized_conversation_input_id = normalize_optional_string(
            conversation_input_id,
            label="RequestContext.conversation_input_id",
        )
        normalized_conversation_input_claim_generation = normalize_optional_non_negative_int(
            conversation_input_claim_generation,
            label="RequestContext.conversation_input_claim_generation",
        )
        normalized_conversation_input_claim_owner = normalize_optional_string(
            conversation_input_claim_owner,
            label="RequestContext.conversation_input_claim_owner",
        )
        normalized_conversation_input_server_boot_id = normalize_optional_string(
            conversation_input_server_boot_id,
            label="RequestContext.conversation_input_server_boot_id",
        )
        normalized_conversation_input_resume_phase = normalize_optional_string(
            conversation_input_resume_phase,
            label="RequestContext.conversation_input_resume_phase",
        )
        normalized_conversation_input_resume_task_id = normalize_optional_string(
            conversation_input_resume_task_id,
            label="RequestContext.conversation_input_resume_task_id",
        )
        normalized_conversation_input_resume_tool_call_id = normalize_optional_string(
            conversation_input_resume_tool_call_id,
            label="RequestContext.conversation_input_resume_tool_call_id",
        )
        normalized_conversation_input_resume_generation = normalize_optional_non_negative_int(
            conversation_input_resume_generation,
            label="RequestContext.conversation_input_resume_generation",
        )
        if access_actions is None:
            normalized_access_actions = frozenset[AccessAction]()
        elif isinstance(access_actions, frozenset) and all(
            isinstance(action, AccessAction) for action in access_actions
        ):
            normalized_access_actions = access_actions
        else:
            raise ValidationError("RequestContext.access_actions must be AccessAction entries.")
        self.trace_id = trace_id_value
        self.client_ip = normalized_client_ip
        self.user_id = user_id
        self.timestamp = timestamp
        self.task_id = normalized_task_id
        self.mutation_fencing_token = normalized_mutation_fencing_token
        self.cancellation_id = normalized_cancellation_id
        self.mcp_tool_context = mcp_tool_context
        self.interactive_tool_approval = interactive_tool_approval
        self.agent_mode = normalized_agent_mode
        self.agent_turn_id = normalized_agent_turn_id
        self.agent_turn_scope = normalized_agent_turn_scope
        self.agent_turn_execution_token = normalized_agent_turn_execution_token
        self.agent_iteration_index = normalized_agent_iteration_index
        self.agent_parent_turn_id = normalized_agent_parent_turn_id
        self.agent_parent_tool_call_id = normalized_agent_parent_tool_call_id
        self.agent_parent_iteration_index = normalized_agent_parent_iteration_index
        self.agent_display_name = normalized_agent_display_name
        self.agent_requested_model = normalized_agent_requested_model
        self.agent_owner_task_id = normalized_agent_owner_task_id
        self.agent_workspace_path = normalized_workspace_path
        self.conversation_input_id = normalized_conversation_input_id
        self.conversation_input_claim_generation = normalized_conversation_input_claim_generation
        self.conversation_input_claim_owner = normalized_conversation_input_claim_owner
        self.conversation_input_server_boot_id = normalized_conversation_input_server_boot_id
        self.conversation_input_resume_phase = normalized_conversation_input_resume_phase
        self.conversation_input_resume_task_id = normalized_conversation_input_resume_task_id
        self.conversation_input_resume_tool_call_id = (
            normalized_conversation_input_resume_tool_call_id
        )
        self.conversation_input_resume_generation = normalized_conversation_input_resume_generation
        self.access_actions = normalized_access_actions


def create_system_context(reason: str) -> RequestContext:
    normalized_reason = reason.strip().lower().replace(" ", "_")
    normalized_reason = normalized_reason or "system"
    trace_id = create_system_id(
        subsystem="context",
        owner=normalized_reason,
        include_random_suffix=True,
    )
    return RequestContext(
        trace_id=trace_id,
        client_ip="internal",
        task_id=trace_id,
        cancellation_id=trace_id,
    )
