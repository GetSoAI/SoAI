"""SoAI - Shared conversation turn request preparation [backend/features/chat/conversation_turn_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.settings_types import AgentSettings
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from core.types.json import JSONDict
from features.agent.runtime.agentic_execution_policy import should_run_agent_turn_engine
from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
from features.agent.runtime.request_assembly import build_agentic_request_assembly
from features.agent.runtime.request_message_source import AgenticRequestMessageSource
from features.agent.subagents.summaries import (
    list_serialized_subagent_snapshots_for_prompt,
)

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("PreparedConversationTurnRequest", "prepare_conversation_turn_request")


@dataclass(frozen=True, slots=True)
class PreparedConversationTurnRequest:
    request_json: JSONDict
    prepared_agent_request: PreparedExecutionRequest | None


async def prepare_conversation_turn_request(
    api_dependencies: ApiDependencies,
    *,
    request_context: RequestContext,
    request_json: JSONDict,
    message_source: AgenticRequestMessageSource,
    user_id: int,
    conv_id: str,
    request_source: RequestSource,
    requested_model: str,
    agent_settings: AgentSettings,
    tool_context: MCPToolContext | None,
    model_settings_snapshot: JSONDict,
    scope_message: JSONDict | None,
    prune_empty_messages: bool,
    stream: bool,
    source_policy: str,
    extra_system_messages: tuple[str, ...] = (),
) -> PreparedConversationTurnRequest:
    todo_state = None
    serialized_subagent_summaries: list[JSONDict] = []
    should_run_agent = should_run_agent_turn_engine(
        agent_settings=agent_settings,
        tool_context=tool_context,
    )
    if should_run_agent:
        todo_state = await api_dependencies.database_agent_todo_state.get_todo_state(
            conv_id=conv_id,
            user_id=user_id,
        )
        serialized_subagent_summaries = await list_serialized_subagent_snapshots_for_prompt(
            database_agent_turns=api_dependencies.database_agent_turns,
            task_registry_queries=api_dependencies.task_registry_queries,
            token_collection=api_dependencies.token_collection,
            conv_id=conv_id,
            user_id=user_id,
        )
    prepared_assembly = await build_agentic_request_assembly(
        api_dependencies=api_dependencies,
        request_json=request_json,
        message_source=message_source,
        user_id=user_id,
        conv_id=conv_id,
        request_source=request_source,
        requested_model=requested_model,
        agent_settings=agent_settings,
        todo_state=todo_state,
        subagent_summaries=serialized_subagent_summaries,
        tool_context=tool_context if should_run_agent else None,
        scope_message=scope_message,
        prune_empty_messages=prune_empty_messages,
        stream=stream,
        source_policy=source_policy,
        summarize_messages=None,
        extra_system_messages=extra_system_messages,
        model_settings_snapshot=model_settings_snapshot,
    )
    request_context.mcp_tool_context = tool_context
    return PreparedConversationTurnRequest(
        request_json=prepared_assembly.effective_request_json,
        prepared_agent_request=prepared_assembly.prepared_agent_request,
    )
