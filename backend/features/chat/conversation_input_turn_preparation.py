"""SoAI - Durable Chat input turn preparation [backend/features/chat/conversation_input_turn_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import CancelledError
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent_mcp_config import normalize_conversation_mcp_config
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.mcp.agent_config_availability import filter_normalized_mcp_to_available_tools
from core.mcp.tool_catalog import collect_mcp_tool_map
from core.mcp.tool_catalog_scope import (
    INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE,
    PUBLIC_MCP_TOOL_CATALOG_SCOPE,
)
from core.mcp.tool_context_preparation import prepare_mcp_tool_context
from core.model_settings.request_projection import build_chat_execution_openai_request
from core.openai.stream_request_preparation import (
    OPENAI_STREAM_FORBIDDEN_FIELDS_WITHOUT_MESSAGES,
    build_openai_stream_request_json,
)
from core.runtime.request_context import RequestContext
from core.runtime.request_context_agent_fields import apply_agent_runtime_context_fields
from core.runtime.request_sources import REQUEST_SOURCE_WEBUI_WS
from core.types.json import JSONDict
from features.agent.runtime.agentic_execution_policy import (
    normalize_tool_context_for_agent_settings,
)
from features.agent.runtime.model_tool_calling import (
    build_supports_tool_calling_callable,
)
from features.agent.runtime.request_message_source import AgenticRequestMessageSource
from features.agent.runtime.request_messages import strip_internal_message_metadata
from features.agent.session.runtime_resolution import resolve_agent_runtime_settings
from features.api.runtime.conversation_mcp_knowledge import (
    apply_knowledge_managed_mcp_overlay,
    resolve_conversation_knowledge_mcp_state,
)
from features.api.runtime.knowledge_prompt_delivery import (
    release_knowledge_prompt_claim_noncritical,
)
from features.api.runtime.tool_request.conversation_context import (
    ToolRequestConversationContext,
)
from features.api.runtime.tool_request.knowledge_prompt_projection import (
    prepare_knowledge_prompt_projection,
    resolve_forced_knowledge_tool_names,
)
from features.api.runtime.webui_attachments.provider_projection import (
    build_webui_attachment_provider_projector,
)
from features.chat.conversation_turn_preparation import (
    prepare_conversation_turn_request,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.mcp.tool_catalog_scope import MCPToolCatalogScope
    from core.orchestrator.types import MCPToolContext
    from core.rag.knowledge_prompt_types import KnowledgePromptDeliveryClaim
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("PreparedConversationInputTurn", "prepare_conversation_input_turn")

LOGGER_NAME = "SoAI.features.chat.conversation_input_turn_preparation"


@dataclass(frozen=True, slots=True)
class PreparedConversationInputTurn:
    request_json: JSONDict
    tool_context: MCPToolContext | None
    prepared_agent_request: PreparedExecutionRequest | None
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None
    agent_settings: AgentSettings
    requested_model: str


def _resolve_tool_catalog_scope(user_record: JSONDict) -> MCPToolCatalogScope:
    if user_record.get("is_admin") is True:
        return INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE
    return PUBLIC_MCP_TOOL_CATALOG_SCOPE


async def prepare_conversation_input_turn(
    api_dependencies: ApiDependencies,
    *,
    request_context: RequestContext,
    conv_id: str,
    user_id: int,
    model_settings_snapshot: JSONDict,
    message_index: int,
    assistant_at_ms: int,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    request_id: str,
) -> PreparedConversationInputTurn:
    runtime_settings = await resolve_agent_runtime_settings(
        api_dependencies,
        user_id=user_id,
        model_settings=model_settings_snapshot,
        request_model=None,
    )
    requested_model = runtime_settings.requested_model
    if not isinstance(requested_model, str) or not requested_model.strip():
        raise ValidationError("Conversation input requires a resolved model.")
    apply_agent_runtime_context_fields(
        context=request_context,
        settings=runtime_settings.settings,
        requested_model=requested_model,
        turn_scope=None,
    )
    canonical_history = await api_dependencies.database_messages.get_canonical_agent_history(
        conv_id,
        user_id,
        before_timestamp_exclusive=assistant_turn_at_ms,
    )
    if canonical_history is None:
        raise StateError("Conversation input canonical history is unavailable.")
    projector = build_webui_attachment_provider_projector(
        dependencies=api_dependencies,
        conv_id=conv_id,
        user_id=user_id,
        model_id=requested_model,
    )
    projected_history = await projector(canonical_history)
    prompt_history = strip_internal_message_metadata(projected_history)
    request_json = build_openai_stream_request_json(
        openai_request=build_chat_execution_openai_request(model_settings_snapshot),
        logger=get_logger(LOGGER_NAME),
        trace_id=request_context.trace_id,
        forbidden_fields=OPENAI_STREAM_FORBIDDEN_FIELDS_WITHOUT_MESSAGES,
        conv_id=conv_id,
        messages=prompt_history,
    )
    conversation = await _prepare_tool_conversation_context(
        api_dependencies,
        conv_id=conv_id,
        user_id=user_id,
        model_settings_snapshot=model_settings_snapshot,
        requested_model=requested_model,
        agent_settings=runtime_settings.settings,
    )
    raw_tool_context = await prepare_mcp_tool_context(
        request_json=request_json,
        agent_mode=conversation.agent_mode,
        normalized_mcp=conversation.normalized_mcp,
        conv_id=conv_id,
        user_id=user_id,
        message_index=message_index,
        assistant_at_ms=assistant_at_ms,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
        model_id=requested_model,
        is_automation=False,
        config=api_dependencies.config,
        force_tool_approval_required=None,
        forced_tool_names=resolve_forced_knowledge_tool_names(
            mode="real_send",
            conversation=conversation,
        ),
        force_tool_choice_auto=True,
        supports_tool_calling=build_supports_tool_calling_callable(api_dependencies),
        sources=api_dependencies,
        local_tool_catalog_scope=conversation.local_tool_catalog_scope,
    )
    tool_context = normalize_tool_context_for_agent_settings(
        agent_settings=runtime_settings.settings,
        tool_context=raw_tool_context,
    )
    request_context.mcp_tool_context = tool_context
    knowledge_prompt = await prepare_knowledge_prompt_projection(
        api_dependencies=api_dependencies,
        conversation=conversation,
        tool_context=tool_context,
        mode="real_send",
        request_id=request_id,
    )
    try:
        prepared_turn = await prepare_conversation_turn_request(
            api_dependencies,
            request_context=request_context,
            request_json=request_json,
            message_source=AgenticRequestMessageSource(
                canonical_messages=canonical_history,
                provider_projector=projector,
            ),
            user_id=user_id,
            conv_id=conv_id,
            request_source=REQUEST_SOURCE_WEBUI_WS,
            requested_model=requested_model,
            agent_settings=runtime_settings.settings,
            tool_context=tool_context,
            model_settings_snapshot=model_settings_snapshot,
            scope_message=None,
            prune_empty_messages=True,
            stream=True,
            source_policy="interactive_conversation",
            extra_system_messages=knowledge_prompt.system_messages,
        )
    except CancelledError:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_dependencies,
                claim=knowledge_prompt.claim,
                logger=get_logger(LOGGER_NAME),
                trace_id=request_context.trace_id,
            ),
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_dependencies,
                claim=knowledge_prompt.claim,
                logger=get_logger(LOGGER_NAME),
                trace_id=request_context.trace_id,
            ),
        )
        raise
    return PreparedConversationInputTurn(
        request_json=prepared_turn.request_json,
        tool_context=tool_context,
        prepared_agent_request=prepared_turn.prepared_agent_request,
        knowledge_prompt_claim=knowledge_prompt.claim,
        agent_settings=runtime_settings.settings,
        requested_model=requested_model,
    )


async def _prepare_tool_conversation_context(
    api_dependencies: ApiDependencies,
    *,
    conv_id: str,
    user_id: int,
    model_settings_snapshot: JSONDict,
    requested_model: str,
    agent_settings: AgentSettings,
) -> ToolRequestConversationContext:
    user_record = await api_dependencies.database_users.get_account_by_id(user_id)
    if not isinstance(user_record, dict):
        raise StateError("Conversation input owner is unavailable.")
    tool_scope = _resolve_tool_catalog_scope(user_record)
    tool_map = await collect_mcp_tool_map(
        api_dependencies.mcp_server,
        api_dependencies.mcp_remote,
        api_dependencies.mcp_tool_catalog_cache,
        local_scope=tool_scope,
    )
    mcp_value = model_settings_snapshot.get("mcp")
    if mcp_value is not None and not isinstance(mcp_value, dict):
        raise ValidationError("Conversation input mcp settings must be an object.")
    normalized_mcp = normalize_conversation_mcp_config(mcp_value)
    knowledge_state = await resolve_conversation_knowledge_mcp_state(
        api_dependencies=api_dependencies,
        conv_id=conv_id,
        model_id=requested_model,
        available_tool_names=set(tool_map),
    )
    normalized_mcp = filter_normalized_mcp_to_available_tools(
        apply_knowledge_managed_mcp_overlay(normalized_mcp, knowledge_state),
        set(tool_map),
    )
    return ToolRequestConversationContext(
        resolved_conv_id=conv_id,
        user_id=user_id,
        is_automation=False,
        requested_model=requested_model,
        settings=model_settings_snapshot,
        agent_settings=agent_settings,
        agent_mode=agent_settings.mode,
        local_tool_catalog_scope=tool_scope,
        normalized_mcp=normalized_mcp,
        knowledge_state=knowledge_state,
    )
