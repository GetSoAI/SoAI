"""SoAI - Shared non-streaming agentic chat dispatch support [backend/features/api/routes/openai/chat/agentic_dispatch_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import Response

from core.runtime.request_context import RequestContext
from features.api.routes.openai.agentic_non_streaming_execution import (
    execute_agentic_request_event_non_streaming,
)
from features.api.routes.openai.chat.chat_ops import (
    resolve_non_streaming_timeout_from_request_json,
)
from features.api.runtime.openai_quota_reservations import (
    release_token_quota_reservation_if_present,
)
from features.api.runtime.openai_request_state import (
    clear_openai_api_key_quota_reservation,
)
from features.api.runtime.responses import create_json_response_with_task_id

if TYPE_CHECKING:
    from core.events.types_models_requests import InferenceRequestReceived
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
    from features.api.routes.openai.agentic_non_streaming_execution import (
        AgenticNonStreamingExecutionResult,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies

__all__ = (
    "AgenticExecutionInputs",
    "AgenticPreparedExecutionRequest",
    "build_agentic_execution_inputs",
    "build_agentic_prepared_execution_request_from_inputs",
    "execute_direct_agentic_response",
    "execute_prepared_agentic_non_streaming",
    "prepare_agentic_async_accept_dispatch",
    "prepare_agentic_direct_dispatch",
    "prepare_agentic_non_streaming_dispatch",
)


@dataclass(frozen=True, slots=True)
class AgenticExecutionInputs:
    request: Request
    api_context: ApiContext
    stream_dependencies: StreamDependencies
    context: RequestContext
    tool_context: MCPToolContext
    prepared_agent_request: PreparedExecutionRequest
    request_event_class: type[InferenceRequestReceived]


@dataclass(frozen=True, slots=True)
class AgenticPreparedExecutionRequest:
    inputs: AgenticExecutionInputs
    timeout_value: float


def build_agentic_execution_inputs(
    *,
    request: Request,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    prepared_agent_request: PreparedExecutionRequest,
    request_event_class: type[InferenceRequestReceived],
) -> AgenticExecutionInputs:
    return AgenticExecutionInputs(
        request=request,
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        context=context,
        tool_context=tool_context,
        prepared_agent_request=prepared_agent_request,
        request_event_class=request_event_class,
    )


def build_agentic_prepared_execution_request_from_inputs(
    *,
    inputs: AgenticExecutionInputs,
    timeout_value: float,
) -> AgenticPreparedExecutionRequest:
    return AgenticPreparedExecutionRequest(
        inputs=inputs,
        timeout_value=timeout_value,
    )


async def prepare_agentic_non_streaming_dispatch(
    request: Request,
    api_context: ApiContext,
    context: RequestContext,
    request_json: JSONDict,
    api_key_id: str | None,
    quota_reservation: JSONDict | None,
    quota_release_operation: str,
) -> float:
    timeout_value = resolve_non_streaming_timeout_from_request_json(request_json)
    await release_token_quota_reservation_if_present(
        api_context,
        api_key_id,
        quota_reservation,
        trace_id=context.trace_id,
        operation=quota_release_operation,
    )
    clear_openai_api_key_quota_reservation(request)
    return timeout_value


async def prepare_agentic_async_accept_dispatch(
    request: Request,
    api_context: ApiContext,
    context: RequestContext,
    request_json: JSONDict,
    api_key_id: str | None,
    quota_reservation: JSONDict | None,
) -> float:
    return await prepare_agentic_non_streaming_dispatch(
        request,
        api_context,
        context,
        request_json,
        api_key_id,
        quota_reservation,
        "api_openai.handle_inference_request.agentic_async.quota_release",
    )


async def prepare_agentic_direct_dispatch(
    request: Request,
    api_context: ApiContext,
    context: RequestContext,
    request_json: JSONDict,
    api_key_id: str | None,
    quota_reservation: JSONDict | None,
) -> float:
    return await prepare_agentic_non_streaming_dispatch(
        request,
        api_context,
        context,
        request_json,
        api_key_id,
        quota_reservation,
        "api_openai.handle_inference_request.agentic_non_streaming.quota_release",
    )


async def execute_prepared_agentic_non_streaming(
    *,
    execution_request: AgenticPreparedExecutionRequest,
    event_type_label: str,
) -> AgenticNonStreamingExecutionResult:
    return await execute_agentic_request_event_non_streaming(
        request=execution_request.inputs.request,
        api_context=execution_request.inputs.api_context,
        stream_dependencies=execution_request.inputs.stream_dependencies,
        context=execution_request.inputs.context,
        tool_context=execution_request.inputs.tool_context,
        prepared_agent_request=execution_request.inputs.prepared_agent_request,
        request_event_class=execution_request.inputs.request_event_class,
        timeout_value=execution_request.timeout_value,
        event_type_label=event_type_label,
    )


async def execute_direct_agentic_response(
    *,
    inputs: AgenticExecutionInputs,
    timeout_value: float,
) -> Response:
    execution = await execute_agentic_request_event_non_streaming(
        request=inputs.request,
        api_context=inputs.api_context,
        stream_dependencies=inputs.stream_dependencies,
        context=inputs.context,
        tool_context=inputs.tool_context,
        prepared_agent_request=inputs.prepared_agent_request,
        request_event_class=inputs.request_event_class,
        timeout_value=timeout_value,
        event_type_label="agentic_loop",
    )
    return create_json_response_with_task_id(
        execution.result.final_payload,
        execution.first_inference_task_id,
        operation_id=inputs.context.trace_id,
    )
