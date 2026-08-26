"""SoAI - Shared conversation MCP state helpers [backend/features/api/runtime/conversation_mcp_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.conversations.settings_authority import (
    ConversationSettingsAuthority,
    resolve_conversation_settings_authority,
)
from core.mcp.agent_config_availability import filter_normalized_mcp_to_available_tools
from core.mcp.agent_config_normalization import (
    NormalizedAgentMCPConfig,
    build_normalized_agent_mcp_config_payload,
)
from core.types.json import JSONDict
from features.api.runtime.conversation_access import resolve_conversation_access_id
from features.api.runtime.conversation_mcp_knowledge import (
    ConversationKnowledgeMCPState,
    apply_knowledge_managed_mcp_overlay,
    build_knowledge_state_payload,
    resolve_conversation_knowledge_mcp_state,
)
from features.api.runtime.conversation_mcp_state_merge import normalize_owner_mcp_config
from features.api.runtime.validation import (
    require_conversation_model_settings_payload,
    require_optional_json_dict,
)
from features.api.runtime.webui_records import webui_fetch_or_404

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from features.api.runtime.context import ApiContext

__all__ = (
    "ConversationMCPState",
    "build_conversation_mcp_config_payload",
    "resolve_conversation_mcp_state",
)


@dataclass(frozen=True, slots=True)
class ConversationMCPState:
    conv_id: str
    settings_authority: ConversationSettingsAuthority
    settings: JSONDict
    stored_normalized_mcp: NormalizedAgentMCPConfig
    effective_normalized_mcp: NormalizedAgentMCPConfig
    knowledge_state: ConversationKnowledgeMCPState

    @property
    def is_automation(self) -> bool:
        return self.settings_authority.is_automation


async def resolve_conversation_mcp_state(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    available_tool_names: set[str] | None = None,
    model_id_override: str | None = None,
    conversation_record: JSONDict | None = None,
) -> ConversationMCPState:
    authoritative_record = conversation_record
    if authoritative_record is None:
        authoritative_record = await webui_fetch_or_404(
            request,
            api_context.dependencies.database_conversations.get_conversation(
                conv_id,
                user_id,
            ),
            message="Conversation not found.",
        )
    resolved_conv_id = resolve_conversation_access_id(authoritative_record, conv_id)
    settings_authority = resolve_conversation_settings_authority(authoritative_record)
    settings = require_conversation_model_settings_payload(
        request,
        settings_authority.model_settings,
    )
    stored_normalized_mcp = normalize_owner_mcp_config(
        request,
        require_optional_json_dict(request, settings.get("mcp"), field="mcp"),
        is_automation=settings_authority.is_automation,
        disallowed_unqualified_tools=load_automation_disallowed_unqualified_tools(
            api_context.dependencies.config,
        ),
    )
    model_id_value = (
        model_id_override if isinstance(model_id_override, str) else settings.get("model")
    )
    model_id = model_id_value if isinstance(model_id_value, str) else None
    knowledge_state = await resolve_conversation_knowledge_mcp_state(
        api_dependencies=api_context.dependencies,
        conv_id=resolved_conv_id,
        model_id=model_id,
        available_tool_names=available_tool_names,
    )
    effective_normalized_mcp = apply_knowledge_managed_mcp_overlay(
        stored_normalized_mcp,
        knowledge_state,
    )
    if available_tool_names is not None:
        effective_normalized_mcp = filter_normalized_mcp_to_available_tools(
            effective_normalized_mcp,
            available_tool_names,
        )
    return ConversationMCPState(
        conv_id=resolved_conv_id,
        settings_authority=settings_authority,
        settings=settings,
        stored_normalized_mcp=stored_normalized_mcp,
        effective_normalized_mcp=effective_normalized_mcp,
        knowledge_state=knowledge_state,
    )


def build_conversation_mcp_config_payload(state: ConversationMCPState) -> JSONDict:
    payload = build_normalized_agent_mcp_config_payload(state.effective_normalized_mcp)
    payload["conv_id"] = state.conv_id
    payload["knowledge_state"] = build_knowledge_state_payload(
        rag_enabled=state.knowledge_state.rag_enabled,
        document_count=state.knowledge_state.document_count,
        auto_managed=state.knowledge_state.auto_managed,
        tools_locked=state.knowledge_state.tools_locked,
        force_tools_enabled=state.knowledge_state.force_tools_enabled,
        ready=state.knowledge_state.ready,
        blocking_reason=state.knowledge_state.blocking_reason,
    )
    return payload
