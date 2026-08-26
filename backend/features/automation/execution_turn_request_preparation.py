"""SoAI - Automation turn request preparation [backend/features/automation/execution_turn_request_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.settings_types import AgentSettings
from core.automation.automation_mcp_config import normalize_automation_mcp_settings
from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.mcp.agent_config_availability import filter_normalized_mcp_to_available_tools
from core.mcp.tool_catalog import collect_mcp_tool_map
from core.mcp.tool_catalog_scope import PUBLIC_MCP_TOOL_CATALOG_SCOPE
from core.mcp.tool_context_preparation import prepare_mcp_tool_context
from core.model_settings.request_projection import build_chat_execution_openai_request
from core.openai.stream_request_preparation import (
    OPENAI_STREAM_FORBIDDEN_FIELDS_WITHOUT_MESSAGES,
    build_openai_stream_request_json,
)
from core.prompts.system_prompts import get_text_prompt_v1
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import REQUEST_SOURCE_AUTOMATION
from features.agent.runtime.agentic_execution_policy import (
    normalize_tool_context_for_agent_settings,
)
from features.agent.runtime.model_tool_calling import (
    build_supports_tool_calling_callable,
)
from features.agent.runtime.request_message_source import AgenticRequestMessageSource
from features.agent.runtime.request_messages import strip_internal_message_metadata
from features.api.runtime.webui_attachments.provider_projection import (
    build_webui_attachment_provider_projector,
)
from features.automation.execution_messages import AutomationConversationSession
from features.chat.conversation_turn_preparation import (
    prepare_conversation_turn_request,
)

if TYPE_CHECKING:
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "PreparedAutomationTurnRequest",
    "prepare_automation_turn_request",
)

LOGGER_NAME = "SoAI.features.automation.execution_turn_request_preparation"


@dataclass(frozen=True, slots=True)
class PreparedAutomationTurnRequest:
    request_json: JSONDict
    tool_context: MCPToolContext | None
    prepared_agent_request: PreparedExecutionRequest | None


async def prepare_automation_turn_request(
    api_dependencies: ApiDependencies,
    *,
    session: AutomationConversationSession,
    request_context: RequestContext,
    conversation_model_settings: JSONDict,
    requested_model: str,
    agent_settings: AgentSettings,
    assistant_at_ms: int,
    assistant_message_index: int,
) -> PreparedAutomationTurnRequest:
    canonical_history = await api_dependencies.database_messages.get_canonical_agent_history(
        session.conv_id,
        session.user_id,
    )
    if canonical_history is None:
        raise StateError("Automation conversation canonical history is unavailable.")
    project_agentic_prompt_messages = build_webui_attachment_provider_projector(
        dependencies=api_dependencies,
        conv_id=session.conv_id,
        user_id=session.user_id,
        model_id=requested_model,
    )
    projected_history = await project_agentic_prompt_messages(canonical_history)
    prompt_history = strip_internal_message_metadata(projected_history)
    request_json = build_openai_stream_request_json(
        openai_request=build_chat_execution_openai_request(
            conversation_model_settings,
        ),
        logger=get_logger(LOGGER_NAME),
        trace_id=request_context.trace_id,
        forbidden_fields=OPENAI_STREAM_FORBIDDEN_FIELDS_WITHOUT_MESSAGES,
        conv_id=session.conv_id,
        messages=prompt_history,
    )
    mcp_value = conversation_model_settings.get("mcp")
    mcp_payload = mcp_value if isinstance(mcp_value, dict) else None
    disallowed_unqualified_tools = load_automation_disallowed_unqualified_tools(
        api_dependencies.config,
    )
    normalized_mcp = normalize_automation_mcp_settings(
        mcp_payload,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    )
    available_tool_map = await collect_mcp_tool_map(
        api_dependencies.mcp_server,
        api_dependencies.mcp_remote,
        api_dependencies.mcp_tool_catalog_cache,
        local_scope=PUBLIC_MCP_TOOL_CATALOG_SCOPE,
    )
    normalized_mcp = filter_normalized_mcp_to_available_tools(
        normalized_mcp,
        set(available_tool_map),
    )
    supports_tool_calling = build_supports_tool_calling_callable(api_dependencies)
    raw_tool_context = await prepare_mcp_tool_context(
        request_json=request_json,
        agent_mode=agent_settings.mode,
        normalized_mcp=normalized_mcp,
        conv_id=session.conv_id,
        user_id=session.user_id,
        message_index=int(assistant_message_index),
        assistant_at_ms=int(assistant_at_ms),
        assistant_turn_at_ms=int(assistant_at_ms),
        model_variant_index=0,
        model_id=requested_model,
        is_automation=True,
        config=api_dependencies.config,
        force_tool_approval_required=None,
        supports_tool_calling=supports_tool_calling,
        sources=api_dependencies,
        local_tool_catalog_scope=PUBLIC_MCP_TOOL_CATALOG_SCOPE,
    )
    tool_context = normalize_tool_context_for_agent_settings(
        agent_settings=agent_settings,
        tool_context=raw_tool_context,
    )
    request_context.mcp_tool_context = tool_context
    prepared_turn = await prepare_conversation_turn_request(
        api_dependencies,
        request_context=request_context,
        request_json=request_json,
        message_source=AgenticRequestMessageSource(
            canonical_messages=canonical_history,
            provider_projector=project_agentic_prompt_messages,
        ),
        user_id=session.user_id,
        conv_id=session.conv_id,
        request_source=REQUEST_SOURCE_AUTOMATION,
        requested_model=requested_model,
        agent_settings=agent_settings,
        tool_context=tool_context,
        scope_message={
            "role": "system",
            "content": get_text_prompt_v1("agent.automation.scope_instruction.v1"),
        },
        prune_empty_messages=False,
        stream=True,
        source_policy="automation_run",
        model_settings_snapshot=conversation_model_settings,
    )
    return PreparedAutomationTurnRequest(
        request_json=prepared_turn.request_json,
        tool_context=tool_context,
        prepared_agent_request=prepared_turn.prepared_agent_request,
    )
