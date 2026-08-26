"""SoAI - MCP tool request preparation [backend/features/api/runtime/tool_request/preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import CancelledError
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import (
    HANDLED_RUNTIME_EXCEPTIONS,
    UNEXPECTED_RUNTIME_EXCEPTIONS,
)
from core.orchestrator.types import MCPToolContext
from core.runtime.protocols import RequestProtocol
from core.runtime.request_context import RequestContext
from core.runtime.request_context_agent_fields import reset_agent_runtime_context_fields
from core.runtime.request_sources import RequestSource
from core.types.json import JSONDict
from core.types.json_value import copy_json_dict
from core.validation.strict_numbers import require_non_negative_int_strict
from features.agent.runtime.agentic_execution_policy import (
    normalize_tool_context_for_agent_settings,
)
from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
from features.agent.runtime.request_message_source import AgenticRequestMessageSource
from features.api.runtime.context import ApiContext
from features.api.runtime.knowledge_prompt_delivery import (
    release_knowledge_prompt_claim_noncritical,
)
from features.api.runtime.tool_request.conversation_context import (
    resolve_tool_request_conversation_context,
)
from features.api.runtime.tool_request.knowledge_prompt_projection import (
    prepare_knowledge_prompt_projection,
    resolve_forced_knowledge_tool_names,
)
from features.api.runtime.tool_request.mcp_tool_context import build_mcp_tool_context
from features.api.runtime.tool_request.message_normalization import (
    normalize_conv_id_and_messages,
)
from features.chat.conversation_turn_preparation import prepare_conversation_turn_request

if TYPE_CHECKING:
    from core.rag.knowledge_prompt_types import KnowledgePromptDeliveryClaim
    from features.api.runtime.tool_request.conversation_context import (
        ToolRequestConversationContext,
    )

__all__ = (
    "PreparedMCPToolRequest",
    "prepare_mcp_tools_for_request",
)


@dataclass(frozen=True, slots=True)
class PreparedMCPToolRequest:
    request_json: JSONDict
    tool_context: MCPToolContext | None
    prepared_agent_request: PreparedExecutionRequest | None
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None


async def prepare_mcp_tools_for_request(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    request_json: JSONDict,
    context: RequestContext,
    request_source: RequestSource,
    message_index: int | None = None,
    assistant_at_ms: int | None = None,
    assistant_turn_at_ms: int | None = None,
    model_variant_index: int | None = None,
    force_tool_approval_required: bool | None = None,
    extra_system_messages: tuple[str, ...] = (),
    knowledge_prompt_mode: Literal["disabled", "projection", "real_send"] = "disabled",
    knowledge_prompt_request_id: str | None = None,
    agentic_message_source: AgenticRequestMessageSource | None = None,
) -> PreparedMCPToolRequest:
    reset_agent_runtime_context_fields(context=context)
    normalized_request_json = copy_json_dict(request_json)
    normalized_conv_id, messages = normalize_conv_id_and_messages(
        request,
        normalized_request_json,
    )
    if normalized_conv_id is None:
        context.mcp_tool_context = None
        return PreparedMCPToolRequest(
            request_json=normalized_request_json,
            tool_context=None,
            prepared_agent_request=None,
            knowledge_prompt_claim=None,
        )
    conversation = await resolve_tool_request_conversation_context(
        request=request,
        api_context=api_context,
        context=context,
        normalized_conv_id=normalized_conv_id,
        request_json=normalized_request_json,
    )
    validated_assistant_turn_at_ms = require_non_negative_int_strict(
        assistant_turn_at_ms,
        error_message="assistant_turn_at_ms is required for MCP tool preparation.",
    )
    validated_model_variant_index = require_non_negative_int_strict(
        model_variant_index,
        error_message="model_variant_index is required for MCP tool preparation.",
    )
    if _should_prepare_knowledge_advisory_without_tools(knowledge_prompt_mode, conversation):
        normalized_request_json.pop("tools", None)
        normalized_request_json["tool_choice"] = "none"
        resolved_tool_context = None
    else:
        tool_context = await build_mcp_tool_context(
            request=request,
            api_context=api_context,
            request_json=normalized_request_json,
            conversation=conversation,
            message_index=message_index,
            assistant_at_ms=assistant_at_ms,
            assistant_turn_at_ms=validated_assistant_turn_at_ms,
            model_variant_index=validated_model_variant_index,
            force_tool_approval_required=force_tool_approval_required,
            forced_tool_names=resolve_forced_knowledge_tool_names(
                mode=knowledge_prompt_mode,
                conversation=conversation,
            ),
            force_tool_choice_auto=True,
        )
        resolved_tool_context = normalize_tool_context_for_agent_settings(
            agent_settings=conversation.agent_settings,
            tool_context=tool_context,
        )
    context.mcp_tool_context = resolved_tool_context
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None = None
    try:
        knowledge_prompt = await prepare_knowledge_prompt_projection(
            api_dependencies=api_context.dependencies,
            conversation=conversation,
            tool_context=resolved_tool_context,
            mode=knowledge_prompt_mode,
            request_id=knowledge_prompt_request_id,
        )
        knowledge_prompt_claim = knowledge_prompt.claim
        prepared_turn = await prepare_conversation_turn_request(
            api_context.dependencies,
            request_context=context,
            request_json=normalized_request_json,
            message_source=(
                agentic_message_source
                if agentic_message_source is not None
                else AgenticRequestMessageSource(canonical_messages=messages)
            ),
            user_id=conversation.user_id,
            conv_id=conversation.resolved_conv_id,
            request_source=request_source,
            requested_model=conversation.requested_model or "",
            agent_settings=conversation.agent_settings,
            tool_context=resolved_tool_context,
            scope_message=None,
            prune_empty_messages=True,
            stream=normalized_request_json.get("stream") is True,
            source_policy="interactive_conversation",
            extra_system_messages=(*extra_system_messages, *knowledge_prompt.system_messages),
            model_settings_snapshot=conversation.settings,
        )
        if resolved_tool_context is not None and prepared_turn.prepared_agent_request is None:
            raise ValidationError("Prepared agent request state is unavailable.")
    except CancelledError:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_context.dependencies,
                claim=knowledge_prompt_claim,
                logger=None,
                trace_id=context.trace_id,
            ),
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_context.dependencies,
                claim=knowledge_prompt_claim,
                logger=None,
                trace_id=context.trace_id,
            ),
        )
        raise
    except UNEXPECTED_RUNTIME_EXCEPTIONS:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_context.dependencies,
                claim=knowledge_prompt_claim,
                logger=None,
                trace_id=context.trace_id,
            ),
        )
        raise
    return PreparedMCPToolRequest(
        request_json=prepared_turn.request_json,
        tool_context=resolved_tool_context,
        prepared_agent_request=prepared_turn.prepared_agent_request,
        knowledge_prompt_claim=knowledge_prompt_claim,
    )


def _should_prepare_knowledge_advisory_without_tools(
    mode: Literal["disabled", "projection", "real_send"],
    conversation: ToolRequestConversationContext,
) -> bool:
    if mode == "disabled":
        return False
    return conversation.knowledge_state.blocking_reason in {
        "model_without_tool_calling",
        "missing_required_tools",
    }
