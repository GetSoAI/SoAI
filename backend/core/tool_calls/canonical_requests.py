"""SoAI - Canonical tool-call persistence request builders [backend/core/tool_calls/canonical_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.database.requests import CreateToolCallRequest
from core.errors.exceptions import StateError
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.tool_calls.storage_identity import build_tool_call_storage_id_from_fields

__all__ = (
    "build_canonical_tool_call_request",
    "build_canonical_tool_call_storage_id",
    "build_pending_collapsed_tool_call_request",
)


def build_canonical_tool_call_storage_id(
    *,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    call_id: str,
) -> str:
    assistant_turn_at_ms = tool_context.assistant_turn_at_ms
    model_variant_index = tool_context.model_variant_index
    if assistant_turn_at_ms is None or model_variant_index is None:
        raise StateError("Tool call persistence requires assistant turn identity.")
    return build_tool_call_storage_id_from_fields(
        conv_id=tool_context.conv_id,
        turn_id=request_context.agent_turn_id,
        iteration_index=request_context.agent_iteration_index,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
        message_index=tool_context.message_index,
        call_id=call_id,
    )


def build_canonical_tool_call_request(
    *,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    call_id: str,
    tool_name: str,
    tool_arguments: str | None,
    status: str,
    sequence_index: int,
    content_index_before: int,
    thinking_index_before: int,
    thinking_duration_before_ms: int | None,
    collapsed: bool,
    error_message: str | None = None,
    tool_result: str | None = None,
    duration_ms: int | None = None,
    started_at_ms: int | None = None,
    created_at_ms: int | None = None,
    completed_at_ms: int | None = None,
    exclusive_claim: bool = False,
) -> CreateToolCallRequest:
    assistant_turn_at_ms = tool_context.assistant_turn_at_ms
    model_variant_index = tool_context.model_variant_index
    if assistant_turn_at_ms is None or model_variant_index is None:
        raise StateError("Tool call persistence requires assistant turn identity.")
    storage_call_id = build_canonical_tool_call_storage_id(
        request_context=request_context,
        tool_context=tool_context,
        call_id=call_id,
    )
    return CreateToolCallRequest(
        call_id=call_id,
        storage_call_id=storage_call_id,
        conv_id=tool_context.conv_id,
        turn_id=request_context.agent_turn_id,
        iteration_index=request_context.agent_iteration_index,
        message_index=tool_context.message_index,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
        assistant_at_ms=tool_context.assistant_at_ms,
        tool_name=tool_name,
        tool_arguments=tool_arguments,
        status=status,
        sequence_index=sequence_index,
        content_index_before=content_index_before,
        thinking_index_before=thinking_index_before,
        thinking_duration_before_ms=thinking_duration_before_ms,
        collapsed=collapsed,
        error_message=error_message,
        tool_result=tool_result,
        duration_ms=duration_ms,
        started_at_ms=started_at_ms,
        created_at_ms=created_at_ms,
        completed_at_ms=completed_at_ms,
        exclusive_claim=exclusive_claim,
    )


def build_pending_collapsed_tool_call_request(
    *,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    call_id: str,
    tool_name: str,
    tool_arguments: str | None,
    sequence_index: int,
    content_index_before: int,
    thinking_index_before: int,
    thinking_duration_before_ms: int | None,
    status: str,
    created_at_ms: int,
) -> CreateToolCallRequest:
    return build_canonical_tool_call_request(
        request_context=request_context,
        tool_context=tool_context,
        call_id=call_id,
        tool_name=tool_name,
        tool_arguments=tool_arguments,
        status=status,
        sequence_index=sequence_index,
        content_index_before=content_index_before,
        thinking_index_before=thinking_index_before,
        thinking_duration_before_ms=thinking_duration_before_ms,
        collapsed=True,
        created_at_ms=created_at_ms,
    )
