"""SoAI - WebSocket prepared chat execution construction [backend/features/api/runtime/chat_execution/websocket_start.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import CancelledError
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import (
    HANDLED_RUNTIME_EXCEPTIONS,
    UNEXPECTED_RUNTIME_EXCEPTIONS,
)
from core.runtime.request_context_cloning import clone_request_context
from features.api.runtime.chat_execution.contracts import (
    PreparedChatExecutionFailure,
    PreparedWebSocketChatExecutionStart,
)
from features.api.runtime.chat_execution.quota import (
    ConversationTurnQuotaDenied,
    ConversationTurnQuotaReservation,
    reserve_conversation_turn_stream_quota,
)
from features.api.runtime.chat_execution.websocket_tools import (
    prepare_websocket_chat_tools,
)
from features.api.runtime.inference_request_model_resolution import (
    require_effective_inference_model_id,
    resolve_effective_inference_model_resolution,
)
from features.api.runtime.knowledge_prompt_delivery import (
    release_knowledge_prompt_claim_noncritical,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.agent.runtime.request_message_source import (
        AgenticRequestMessageSource,
    )
    from features.api.runtime.context import ApiContext

__all__ = ("prepare_websocket_chat_execution_start",)


async def prepare_websocket_chat_execution_start(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    request_json: JSONDict,
    request_id: str,
    user_id: int,
    message_index: int,
    assistant_at_ms: int,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    extra_system_messages: tuple[str, ...],
    trace_id: str | None,
    logger: LoggerProtocol,
    agentic_message_source: AgenticRequestMessageSource | None = None,
) -> PreparedWebSocketChatExecutionStart | PreparedChatExecutionFailure:
    request_context = clone_request_context(
        request.state.context,
        interactive_tool_approval=True,
    )
    request_context.mcp_tool_context = None
    prepared_tools, tool_error_code, tool_error_message = await prepare_websocket_chat_tools(
        request=request,
        api_context=api_context,
        request_context=request_context,
        request_json=request_json,
        trace_id=trace_id,
        logger=logger,
        message_index=message_index,
        assistant_at_ms=assistant_at_ms,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
        extra_system_messages=extra_system_messages,
        request_id=request_id,
        agentic_message_source=agentic_message_source,
    )
    if prepared_tools is None:
        return PreparedChatExecutionFailure(
            error_code=tool_error_code or "invalid_request_error",
            error_message=tool_error_message or "Failed to prepare MCP tools.",
        )
    prepared_request_json = prepared_tools.request_json
    prepared_agent_request = prepared_tools.prepared_agent_request
    effective_request_json = (
        prepared_agent_request.final_payload
        if prepared_agent_request is not None
        else prepared_request_json
    )
    try:
        model_resolution = resolve_effective_inference_model_resolution(
            request_json=effective_request_json,
            request_context=request_context,
            prepared_agent_request=prepared_agent_request,
            apply_to_request_json=True,
        )
        effective_model_id = require_effective_inference_model_id(
            resolution=model_resolution,
            error_message="Chat stream start requires a resolved model.",
        )
    except ValidationError as exception:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_context.dependencies,
                claim=prepared_tools.knowledge_prompt_claim,
                logger=logger,
                trace_id=trace_id,
            ),
        )
        return PreparedChatExecutionFailure(
            error_code="invalid_request_error",
            error_message=str(exception),
        )
    except CancelledError:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_context.dependencies,
                claim=prepared_tools.knowledge_prompt_claim,
                logger=logger,
                trace_id=trace_id,
            ),
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_context.dependencies,
                claim=prepared_tools.knowledge_prompt_claim,
                logger=logger,
                trace_id=trace_id,
            ),
        )
        raise
    except UNEXPECTED_RUNTIME_EXCEPTIONS:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_context.dependencies,
                claim=prepared_tools.knowledge_prompt_claim,
                logger=logger,
                trace_id=trace_id,
            ),
        )
        raise
    try:
        quota_key_id, quota_token_reservation, quota_error = await _reserve_user_quota(
            api_context=api_context,
            user_id=user_id,
            request_json=model_resolution.request_json,
            logger=logger,
        )
    except CancelledError:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_context.dependencies,
                claim=prepared_tools.knowledge_prompt_claim,
                logger=logger,
                trace_id=trace_id,
            ),
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_context.dependencies,
                claim=prepared_tools.knowledge_prompt_claim,
                logger=logger,
                trace_id=trace_id,
            ),
        )
        raise
    except UNEXPECTED_RUNTIME_EXCEPTIONS:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_context.dependencies,
                claim=prepared_tools.knowledge_prompt_claim,
                logger=logger,
                trace_id=trace_id,
            ),
        )
        raise
    if quota_error is not None:
        await uncancel_then_cleanup(
            release_knowledge_prompt_claim_noncritical(
                api_dependencies=api_context.dependencies,
                claim=prepared_tools.knowledge_prompt_claim,
                logger=logger,
                trace_id=trace_id,
            ),
        )
        return quota_error
    return PreparedWebSocketChatExecutionStart(
        request_context=request_context,
        request_json=model_resolution.request_json,
        effective_model_id=effective_model_id,
        tool_context=prepared_tools.tool_context,
        prepared_agent_request=prepared_agent_request,
        quota_key_id=quota_key_id,
        quota_token_reservation=quota_token_reservation,
        knowledge_prompt_claim=prepared_tools.knowledge_prompt_claim,
    )


async def _reserve_user_quota(
    *,
    api_context: ApiContext,
    user_id: int,
    request_json: JSONDict,
    logger: LoggerProtocol,
) -> tuple[str | None, JSONDict | None, PreparedChatExecutionFailure | None]:
    if user_id <= 0:
        return (None, None, None)
    quota_result = await reserve_conversation_turn_stream_quota(
        api_dependencies=api_context.dependencies,
        user_id=user_id,
        request_json=request_json,
        logger=logger,
    )
    if isinstance(quota_result, ConversationTurnQuotaDenied):
        return (
            None,
            None,
            PreparedChatExecutionFailure(
                error_code="quota_exceeded",
                error_message=quota_result.message,
            ),
        )
    if isinstance(quota_result, ConversationTurnQuotaReservation):
        return (quota_result.key_id, quota_result.token_reservation, None)
    return (None, None, None)
