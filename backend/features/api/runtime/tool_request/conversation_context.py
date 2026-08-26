"""SoAI - MCP tool request conversation context [backend/features/api/runtime/tool_request/conversation_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent_mcp_config import normalize_conversation_mcp_config
from core.automation.automation_mcp_config import normalize_automation_mcp_settings
from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.conversations.conversation_model_settings_resolution import (
    resolve_conversation_model_settings,
)
from core.errors.exceptions import ValidationError
from core.mcp.agent_config_normalization import (
    NormalizedAgentMCPConfig,
    build_normalized_agent_mcp_config_payload,
)
from core.mcp.tool_catalog_scope import (
    INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE,
    PUBLIC_MCP_TOOL_CATALOG_SCOPE,
    MCPToolCatalogScope,
)
from core.openai.request_fields import resolve_optional_model_name
from core.runtime.request_context_agent_fields import apply_agent_runtime_context_fields
from features.agent.runtime.execution_preparation import resolve_agent_request_settings
from features.api.runtime.conversation_mcp_catalog_state import (
    load_conversation_mcp_catalog_state,
)
from features.api.runtime.conversation_mcp_knowledge import (
    apply_knowledge_managed_mcp_overlay,
)
from features.api.runtime.request_user_resolution import resolve_request_user_id

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.runtime.protocols import RequestProtocol
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.runtime.conversation_mcp_knowledge import (
        ConversationKnowledgeMCPState,
    )

__all__ = (
    "ToolRequestConversationContext",
    "resolve_tool_request_conversation_context",
)


@dataclass(frozen=True, slots=True)
class ToolRequestConversationContext:
    resolved_conv_id: str
    user_id: int
    is_automation: bool
    requested_model: str | None
    settings: JSONDict
    agent_settings: AgentSettings
    agent_mode: str
    local_tool_catalog_scope: MCPToolCatalogScope
    normalized_mcp: NormalizedAgentMCPConfig
    knowledge_state: ConversationKnowledgeMCPState


async def resolve_tool_request_conversation_context(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    context: RequestContext,
    normalized_conv_id: str,
    request_json: JSONDict,
) -> ToolRequestConversationContext:
    user_id = resolve_request_user_id(request)
    user_record = await api_context.dependencies.database_users.get_account_by_id(user_id)
    user_is_admin = isinstance(user_record, Mapping) and user_record.get("is_admin") is True
    local_tool_catalog_scope = (
        INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE if user_is_admin else PUBLIC_MCP_TOOL_CATALOG_SCOPE
    )
    request_model = resolve_optional_model_name(request_json)
    state, _tool_map = await load_conversation_mcp_catalog_state(
        request=request,
        api_context=api_context,
        conv_id=normalized_conv_id,
        user_id=user_id,
        local_tool_catalog_scope=local_tool_catalog_scope,
        model_id_override=request_model,
    )
    if state.is_automation:
        local_tool_catalog_scope = PUBLIC_MCP_TOOL_CATALOG_SCOPE
    settings = dict(state.settings)
    if request_model is not None:
        settings["model"] = request_model
    settings = await resolve_conversation_model_settings(
        user_id=user_id,
        model_settings_snapshot=settings,
        database_chat_identity_defaults=(api_context.dependencies.database_chat_identity_defaults),
        database_chat_model_defaults=api_context.dependencies.database_chat_model_defaults,
    )
    normalized_mcp = state.effective_normalized_mcp
    mcp_override_raw = request_json.get("mcp")
    if mcp_override_raw is not None and not isinstance(mcp_override_raw, dict):
        raise ValidationError("mcp must be an object when provided.")
    if isinstance(mcp_override_raw, dict):
        merged_mcp_config_payload = {
            **build_normalized_agent_mcp_config_payload(normalized_mcp),
            **dict(mcp_override_raw),
        }
        if state.is_automation:
            normalized_mcp = normalize_automation_mcp_settings(
                merged_mcp_config_payload,
                disallowed_unqualified_tools=load_automation_disallowed_unqualified_tools(
                    api_context.dependencies.config,
                ),
            )
        else:
            normalized_mcp = normalize_conversation_mcp_config(
                merged_mcp_config_payload,
                allow_extensions=False,
            )
        normalized_mcp = apply_knowledge_managed_mcp_overlay(
            normalized_mcp,
            state.knowledge_state,
        )
        settings["mcp"] = build_normalized_agent_mcp_config_payload(normalized_mcp)
    else:
        settings["mcp"] = build_normalized_agent_mcp_config_payload(normalized_mcp)
    requested_model, _, agent_settings = await resolve_agent_request_settings(
        request=request,
        api_dependencies=api_context.dependencies,
        user_id=user_id,
        request_json=request_json,
        model_settings=settings,
    )
    agent_mode = agent_settings.mode
    apply_agent_runtime_context_fields(
        context=context,
        settings=agent_settings,
        requested_model=requested_model,
        turn_scope=None,
    )
    return ToolRequestConversationContext(
        resolved_conv_id=state.conv_id,
        user_id=user_id,
        is_automation=state.is_automation,
        requested_model=requested_model,
        settings=settings,
        agent_settings=agent_settings,
        agent_mode=agent_mode,
        local_tool_catalog_scope=local_tool_catalog_scope,
        normalized_mcp=normalized_mcp,
        knowledge_state=state.knowledge_state,
    )
