"""SoAI - Shared non-streaming agentic execution [backend/features/api/routes/openai/agentic_non_streaming_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.tasks.type_catalog import TaskTypeId
from features.agent.runtime.execution_preparation import prepare_agent_runtime
from features.agent.runtime.non_streaming_turn_engine import run_non_streaming_turn
from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
from features.api.routes.openai.agent_compaction_optional_summarizer import (
    prepare_optional_compaction_summarizer,
)
from features.api.routes.openai.agent_inference_payload_waiter import (
    await_agent_inference_payload,
)
from features.api.routes.openai.agent_inference_task_creation import (
    create_agent_inference_task,
)
from features.api.routes.openai.agent_route_execution import (
    create_agent_iteration_context,
    prepare_agent_route_execution,
)
from features.api.runtime.chat_execution.request_resolution import resolve_task_type

if TYPE_CHECKING:
    from fastapi import Request

    from core.events.types_models_requests import InferenceRequestReceived
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.agent.runtime.turn_engine import AgentTurnResult
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies

__all__ = (
    "AgenticNonStreamingExecutionResult",
    "execute_agentic_non_streaming",
    "execute_agentic_request_event_non_streaming",
)

LOGGER_NAME = "SoAI.features.api.agentic_non_streaming_execution"


@dataclass(frozen=True, slots=True)
class AgenticNonStreamingExecutionResult:
    result: AgentTurnResult
    first_inference_task_id: str


async def execute_agentic_request_event_non_streaming(
    *,
    request: Request,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    prepared_agent_request: PreparedExecutionRequest,
    request_event_class: type[InferenceRequestReceived],
    timeout_value: float,
    event_type_label: str,
) -> AgenticNonStreamingExecutionResult:
    return await execute_agentic_non_streaming(
        request=request,
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        context=context,
        tool_context=tool_context,
        prepared_agent_request=prepared_agent_request,
        task_type=resolve_task_type(request_event_class),
        timeout_value=timeout_value,
        event_type_label=event_type_label,
    )


async def execute_agentic_non_streaming(
    *,
    request: Request,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    prepared_agent_request: PreparedExecutionRequest,
    task_type: TaskTypeId,
    timeout_value: float,
    event_type_label: str,
) -> AgenticNonStreamingExecutionResult:
    logger = get_logger(LOGGER_NAME)
    prepared_agent = prepared_agent_request
    prepared_execution = await prepare_agent_route_execution(
        request=request,
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        context=context,
        tool_context=tool_context,
        prepared_agent_request=prepared_agent,
        task_type=task_type,
        logger=logger,
        prepare_runtime=prepare_agent_runtime,
        prepare_summarizer=prepare_optional_compaction_summarizer,
    )
    runtime_preparation = prepared_execution.runtime_preparation
    response_task_id: str | None = None

    async def make_inference_request(
        iteration_index: int,
        payload: JSONDict,
        cancellation_id: str,
    ) -> JSONDict:
        nonlocal response_task_id
        iteration_context = create_agent_iteration_context(
            context,
            cancellation_id=cancellation_id,
            agent_iteration_index=iteration_index,
        )
        iteration_bundle = await create_agent_inference_task(
            request,
            api_context,
            context=iteration_context,
            payload=payload,
            task_type=task_type,
            owner_type=runtime_preparation.owner_type,
            owner_id=runtime_preparation.owner_id,
            cancellation_id=cancellation_id,
            event_type_label=event_type_label,
        )
        if response_task_id is None:
            response_task_id = iteration_bundle.task.task_id
        converter_format: Literal["chat", "completions"]
        if "completions" in iteration_bundle.required_capabilities:
            converter_format = "completions"
        else:
            converter_format = "chat"
        allow_image_events = "images" in iteration_bundle.required_capabilities
        return await await_agent_inference_payload(
            request,
            stream_dependencies,
            iteration_context,
            iteration_bundle.payload,
            iteration_bundle.reply_queue,
            iteration_bundle.task.task_id,
            timeout_value,
            allow_image_events=allow_image_events,
            converter_format=converter_format,
        )

    result = await run_non_streaming_turn(
        deps=runtime_preparation.deps,
        context=context,
        tool_context=tool_context,
        initial_messages=prepared_execution.initial_messages,
        initial_boundary_source_messages=prepared_execution.initial_boundary_source_messages,
        base_request_payload=prepared_execution.base_request_payload,
        settings=runtime_preparation.settings,
        make_inference_request=make_inference_request,
        summarize_messages=prepared_execution.summarize_messages,
        prepared_auto_compaction=prepared_execution.prepared_auto_compaction,
        turn_id=context.agent_turn_id,
    )
    if response_task_id is None or not response_task_id.strip():
        raise StateError("Agentic non-streaming execution did not create an inference task.")
    return AgenticNonStreamingExecutionResult(
        result=result,
        first_inference_task_id=response_task_id,
    )
