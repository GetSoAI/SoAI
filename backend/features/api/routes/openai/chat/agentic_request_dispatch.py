"""SoAI - Direct non-streaming agentic chat dispatch [backend/features/api/routes/openai/chat/agentic_request_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import Response

from core.errors.exceptions import ValidationError
from core.events.types_models_requests import InferenceRequestReceived
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from features.api.routes.openai.chat.agentic_dispatch_support import (
    build_agentic_execution_inputs,
    execute_direct_agentic_response,
    prepare_agentic_direct_dispatch,
)
from features.api.runtime.context import ApiContext
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest

__all__ = ("maybe_execute_direct_agentic_request",)


async def maybe_execute_direct_agentic_request(
    *,
    request: Request,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    request_json: JSONDict,
    tool_context: MCPToolContext | None,
    prepared_agent_request: PreparedExecutionRequest | None,
    prepared_agent_turn: bool,
    request_event_class: type[InferenceRequestReceived],
    async_accept_requested: bool,
    is_streaming: bool,
    api_key_id: str | None,
    quota_reservation: JSONDict | None,
) -> Response | None:
    if tool_context is None or async_accept_requested or is_streaming:
        return None
    if prepared_agent_turn and prepared_agent_request is None:
        raise ValidationError("Prepared agent turn state is inconsistent.")
    if not prepared_agent_turn or prepared_agent_request is None:
        return None
    timeout_value = await prepare_agentic_direct_dispatch(
        request,
        api_context,
        context,
        request_json,
        api_key_id,
        quota_reservation,
    )
    request_event = request_event_class
    execution_inputs = build_agentic_execution_inputs(
        request_event_class=request_event,
        prepared_agent_request=prepared_agent_request,
        tool_context=tool_context,
        context=context,
        stream_dependencies=stream_dependencies,
        api_context=api_context,
        request=request,
    )
    return await execute_direct_agentic_response(
        inputs=execution_inputs,
        timeout_value=timeout_value,
    )
