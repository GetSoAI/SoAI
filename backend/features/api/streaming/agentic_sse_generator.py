"""SoAI - Agentic SSE stream generator shared by API and WebUI [backend/features/api/streaming/agentic_sse_generator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.openai.sse_events import format_openai_stream_error_chunk
from core.openai.sse_frames import sse_done_chunk
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.task import Task
from core.tasks.type_catalog import TASK_TYPE_CHAT_COMPLETION
from features.agent.runtime.execution_preparation import prepare_agent_runtime
from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
from features.agent.runtime.streaming_inference_runner_callbacks import (
    build_agent_streaming_inference_runner,
)
from features.api.routes.openai.agent_compaction_optional_summarizer import (
    prepare_optional_compaction_summarizer,
)
from features.api.routes.openai.agent_route_execution import (
    create_agent_iteration_context,
    prepare_agent_route_execution,
)
from features.api.runtime.context import ApiContext
from features.api.streaming.agentic_sse_engine import run_agentic_sse_engine
from features.api.streaming.agentic_sse_engine_task_lifecycle import (
    attach_engine_task_completion_signal,
)
from features.api.streaming.agentic_sse_output_bridge import AgenticSseOutputBridge
from features.api.streaming.openai_streaming_runner_overrides import (
    build_openai_streaming_runner_overrides,
)
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.openai.token_accounting import PromptOccupancy
    from core.openai.usage.models import CanonicalUsage
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.agent.internal_protocols import AgentStreamingInferenceRunnerProtocol
    from features.agent.runtime.turn_iteration_policy_types import (
        AgentOutputPublicationMode,
    )
    from features.api.runtime.preview_contract_output_validation import (
        PreviewContractOutputValidationResult,
    )

__all__ = ("create_agentic_sse_stream_generator",)

LOGGER_NAME = "SoAI.features.api.agentic_sse_generator"


async def create_agentic_sse_stream_generator(
    request: RequestProtocol,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    task: Task | None,
    initial_reply_queue: asyncio.Queue[Event] | None,
    required_capabilities: tuple[str, ...],
    required_modalities: tuple[str, ...],
    prepared_agent_request: PreparedExecutionRequest | None,
    *,
    request_source: RequestSource,
    format_error_chunk: Callable[[str, str, str], str] | None = None,
    include_usage: bool = False,
    cancel_on_disconnect: bool | None = None,
    on_inference_payload_prepared: Callable[[JSONDict], Awaitable[None] | None] | None = None,
    on_compacted_prompt_occupancy: Callable[[PromptOccupancy], None] | None = None,
    on_visible_usage_resolved: Callable[[CanonicalUsage], Awaitable[None] | None] | None = None,
    on_iteration_task_ready: Callable[[Task, int], Awaitable[None] | None] | None = None,
    create_iteration_task: (
        Callable[
            [
                JSONDict,
                RequestContext,
                str,
                Callable[[bytes], Awaitable[None] | None],
            ],
            Awaitable[tuple[Task, asyncio.Queue[Event]]],
        ]
        | None
    ) = None,
    validate_visible_assistant_output: (
        Callable[
            [str],
            Awaitable[PreviewContractOutputValidationResult],
        ]
        | None
    ) = None,
    initial_output_publication_mode: AgentOutputPublicationMode | None = None,
    first_iteration_cancellation_id: str | None = None,
    acknowledge_stream_consumption: bool = False,
) -> AsyncGenerator[bytes]:
    logger = get_logger(LOGGER_NAME)
    done_chunk = sse_done_chunk()
    _ = (required_capabilities, required_modalities)
    task_type = task.task_type if task is not None else TASK_TYPE_CHAT_COMPLETION
    trace_id = context.trace_id
    tool_context_value = context.mcp_tool_context
    tool_context = tool_context_value if isinstance(tool_context_value, MCPToolContext) else None
    if tool_context is None:
        error_bytes = format_openai_stream_error_chunk(
            format_error_chunk,
            "MCP tools are not available for this request.",
            "service_unavailable",
            trace_id,
        )
        yield error_bytes
        yield done_chunk
        return
    if prepared_agent_request is None:
        error_bytes = format_openai_stream_error_chunk(
            format_error_chunk,
            "Prepared agent request state is unavailable.",
            "server_error",
            trace_id,
        )
        yield error_bytes
        yield done_chunk
        return
    prepared_execution = await prepare_agent_route_execution(
        request=request,
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        context=context,
        tool_context=tool_context,
        prepared_agent_request=prepared_agent_request,
        task_type=task_type,
        logger=logger,
        prepare_runtime=prepare_agent_runtime,
        prepare_summarizer=prepare_optional_compaction_summarizer,
    )
    runtime_preparation = prepared_execution.runtime_preparation
    overrides = build_openai_streaming_runner_overrides(
        request=request,
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        trace_id=context.trace_id,
        task_type=task_type,
        owner_type=runtime_preparation.owner_type,
        owner_id=runtime_preparation.owner_id,
        format_error_chunk=format_error_chunk,
        model=runtime_preparation.requested_model,
        event_type_label="agentic_stream",
    )
    streaming_inference_runner: AgentStreamingInferenceRunnerProtocol = (
        build_agent_streaming_inference_runner(
            api_context.dependencies,
            context=context,
            initial_task=task,
            initial_reply_queue=initial_reply_queue,
            task_type=task_type,
            user_id=int(context.user_id),
            owner_type=runtime_preparation.owner_type,
            owner_id=runtime_preparation.owner_id,
            metadata=(
                dict(task.metadata) if task is not None and isinstance(task.metadata, dict) else {}
            ),
            model=runtime_preparation.requested_model,
            request_source=request_source,
            token_estimation_profile=runtime_preparation.settings.token_estimation_profile,
            build_context=create_agent_iteration_context,
            create_additional_task=(
                create_iteration_task
                if create_iteration_task is not None
                else overrides.create_additional_task
            ),
            stream_generator_factory=overrides.create_stream_generator,
            cancellation_history=api_context.dependencies.cancellation_history,
            on_task_ready=on_iteration_task_ready,
        )
    )
    bridge = AgenticSseOutputBridge(
        logger=logger,
        done_chunk=done_chunk,
        acknowledge_stream_consumption=acknowledge_stream_consumption,
    )
    initial_task_cancellation_id = (
        task.cancellation_id.strip()
        if task is not None
        and isinstance(task.cancellation_id, str)
        and task.cancellation_id.strip()
        else None
    )
    if first_iteration_cancellation_id is not None and first_iteration_cancellation_id.strip():
        initial_task_cancellation_id = first_iteration_cancellation_id.strip()

    async def run_engine() -> None:
        await run_agentic_sse_engine(
            context=context,
            trace_id=trace_id,
            logger=logger,
            format_error_chunk=format_error_chunk,
            base_request_payload=prepared_execution.base_request_payload,
            tool_context=tool_context,
            runtime_preparation=runtime_preparation,
            message_history=prepared_execution.initial_messages,
            boundary_source_messages=prepared_agent_request.boundary_source_messages,
            streaming_inference_runner=streaming_inference_runner,
            on_inference_payload_prepared=on_inference_payload_prepared,
            on_pre_compaction_prompt_occupancy=None,
            on_compacted_prompt_occupancy=on_compacted_prompt_occupancy,
            on_visible_usage_resolved=on_visible_usage_resolved,
            include_usage=include_usage,
            summarize_messages=prepared_execution.summarize_messages,
            first_iteration_cancellation_id=initial_task_cancellation_id,
            prepared_auto_compaction=prepared_execution.prepared_auto_compaction,
            validate_visible_assistant_output=validate_visible_assistant_output,
            initial_output_publication_mode=initial_output_publication_mode,
            detach_event=bridge.detach_event,
            push_bytes=bridge.push_bytes,
        )

    engine_task = spawn_tracked_task(
        run_engine(),
        name="openai-agentic-stream-engine",
        logger=logger,
        cancellation_binder=api_context.dependencies.task_cancellation_binder,
        cancellation_id=context.cancellation_id,
        owner="api_openai.agentic_stream",
        finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
        owner_observes_result=True,
    )
    attach_engine_task_completion_signal(engine_task, bridge.stream_stop_event)
    api_context.dependencies.application_control.track_background_task(engine_task)
    cancel_engine_on_detach = (
        bool(cancel_on_disconnect) if cancel_on_disconnect is not None else False
    )
    async for chunk in bridge.stream_bytes(
        engine_task=engine_task,
        cancel_engine_on_detach=cancel_engine_on_detach,
        trace_id=trace_id,
    ):
        yield chunk
