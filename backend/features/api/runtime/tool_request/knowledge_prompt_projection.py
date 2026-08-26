"""SoAI - WebUI Knowledge prompt projection [backend/features/api/runtime/tool_request/knowledge_prompt_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import CancelledError
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.concurrency.cancellation_cleanup import (
    run_idempotent_current_task_operation,
    uncancel_then_cleanup,
)
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import (
    HANDLED_RUNTIME_EXCEPTIONS,
    UNEXPECTED_RUNTIME_EXCEPTIONS,
)
from core.orchestrator.types import MCPToolContext
from core.rag.knowledge_prompt_contract import (
    KNOWLEDGE_ACCESS_TOOL_NAMES,
    KNOWLEDGE_PROMPT_CLAIM_TTL_MS,
    KNOWLEDGE_PROMPT_MAX_PENDING_EVENTS,
)
from core.rag.knowledge_prompt_rendering import render_knowledge_prompt
from core.rag.knowledge_prompt_types import KnowledgePromptDeliveryClaim
from core.runtime.soai_identifiers import create_system_id
from core.timing.epoch import epoch_ms
from features.api.runtime.knowledge_prompt_delivery import (
    release_knowledge_prompt_claim_noncritical,
)

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies
    from features.api.runtime.tool_request.conversation_context import (
        ToolRequestConversationContext,
    )

__all__ = (
    "PreparedKnowledgePromptProjection",
    "prepare_knowledge_prompt_projection",
    "resolve_forced_knowledge_tool_names",
)


@dataclass(frozen=True, slots=True)
class PreparedKnowledgePromptProjection:
    system_messages: tuple[str, ...]
    claim: KnowledgePromptDeliveryClaim | None


def resolve_forced_knowledge_tool_names(
    *,
    mode: Literal["disabled", "projection", "real_send"],
    conversation: ToolRequestConversationContext,
) -> tuple[str, ...]:
    if mode == "disabled":
        return ()
    state = conversation.knowledge_state
    if not state.rag_enabled or state.document_count <= 0 or not state.ready:
        return ()
    return KNOWLEDGE_ACCESS_TOOL_NAMES


async def prepare_knowledge_prompt_projection(
    *,
    api_dependencies: ApiDependencies,
    conversation: ToolRequestConversationContext,
    tool_context: MCPToolContext | None,
    mode: Literal["disabled", "projection", "real_send"],
    request_id: str | None,
) -> PreparedKnowledgePromptProjection:
    if mode == "disabled":
        return PreparedKnowledgePromptProjection((), None)
    if mode == "real_send" and (request_id is None or not request_id.strip()):
        raise ValidationError("Knowledge prompt delivery requires a request id.")
    visible_tool_names = (
        tuple(tool_context.visible_tool_names)
        if isinstance(tool_context, MCPToolContext) and tool_context.visible_tool_names
        else ()
    )
    prompt_state = api_dependencies.database_knowledge_prompt_state
    inputs = await prompt_state.load_prompt_projection_inputs(
        conv_id=conversation.resolved_conv_id,
        user_id=conversation.user_id,
        max_pending_events=KNOWLEDGE_PROMPT_MAX_PENDING_EVENTS,
        max_documents=KNOWLEDGE_PROMPT_MAX_PENDING_EVENTS,
    )
    rendered = render_knowledge_prompt(
        inputs=inputs,
        visible_tool_names=visible_tool_names,
        model_supports_tools=conversation.knowledge_state.ready,
    )
    if rendered.system_message is None:
        return PreparedKnowledgePromptProjection((), None)
    if mode == "projection":
        return PreparedKnowledgePromptProjection((rendered.system_message,), None)
    claim = await _claim_delivery(
        api_dependencies=api_dependencies,
        conversation=conversation,
        request_id=str(request_id),
        event_ceiling_id=rendered.event_ceiling_id,
        state_signature=rendered.state_signature,
    )
    if claim is None:
        return PreparedKnowledgePromptProjection((), None)
    return PreparedKnowledgePromptProjection((rendered.system_message,), claim)


async def _claim_delivery(
    *,
    api_dependencies: ApiDependencies,
    conversation: ToolRequestConversationContext,
    request_id: str,
    event_ceiling_id: int,
    state_signature: str,
) -> KnowledgePromptDeliveryClaim | None:
    now_ms = int(epoch_ms())
    claim_id = create_system_id(
        subsystem="knowledge_prompt",
        owner="delivery_claim",
        include_random_suffix=True,
    )
    cleanup_claim = KnowledgePromptDeliveryClaim(
        conv_id=conversation.resolved_conv_id,
        user_id=conversation.user_id,
        claim_id=claim_id,
        request_id=request_id,
        event_ceiling_id=event_ceiling_id,
        state_signature=state_signature,
    )
    prompt_state = api_dependencies.database_knowledge_prompt_state
    try:
        result = await run_idempotent_current_task_operation(
            lambda: prompt_state.create_or_reuse_delivery_claim(
                conv_id=conversation.resolved_conv_id,
                user_id=conversation.user_id,
                request_id=request_id,
                claim_id=claim_id,
                event_ceiling_id=event_ceiling_id,
                state_signature=state_signature,
                expires_at_ms=now_ms + KNOWLEDGE_PROMPT_CLAIM_TTL_MS,
                now_ms=now_ms,
            ),
        )
        if not result.claimed:
            return None
        if result.claim_id is None or result.request_id is None:
            raise ValidationError("Knowledge prompt delivery claim is invalid.")
        cleanup_claim = KnowledgePromptDeliveryClaim(
            conv_id=conversation.resolved_conv_id,
            user_id=conversation.user_id,
            claim_id=result.claim_id,
            request_id=result.request_id,
            event_ceiling_id=event_ceiling_id,
            state_signature=state_signature,
        )
        if result.event_ceiling_id is None or result.state_signature is None:
            raise ValidationError("Knowledge prompt delivery claim payload is invalid.")
        if result.event_ceiling_id != event_ceiling_id or result.state_signature != state_signature:
            raise ValidationError("Knowledge prompt delivery claim state changed.")
        return KnowledgePromptDeliveryClaim(
            conv_id=conversation.resolved_conv_id,
            user_id=conversation.user_id,
            claim_id=result.claim_id,
            request_id=result.request_id,
            event_ceiling_id=result.event_ceiling_id,
            state_signature=result.state_signature,
        )
    except CancelledError:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_dependencies,
                claim=cleanup_claim,
                logger=None,
                trace_id=None,
            ),
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_dependencies,
                claim=cleanup_claim,
                logger=None,
                trace_id=None,
            ),
        )
        raise
    except UNEXPECTED_RUNTIME_EXCEPTIONS:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_dependencies,
                claim=cleanup_claim,
                logger=None,
                trace_id=None,
            ),
        )
        raise
