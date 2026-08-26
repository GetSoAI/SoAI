"""SoAI - WebSocket agent chat stream construction [backend/features/api/routes/system/events/websocket_chat_stream/agent_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import Queue
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TYPE_CHECKING

from core.openai.token_accounting import count_prompt_occupancy_async
from core.openai.usage.serialization import build_internal_usage_payload
from core.runtime.request_sources import REQUEST_SOURCE_WEBUI_WS
from core.tasks.type_catalog import TASK_TYPE_CHAT_COMPLETION
from features.agent.runtime.streaming_inference_admission import (
    create_streaming_inference_task,
)
from features.agent.runtime.turn_iteration_policy_types import (
    AgentOutputPublicationMode,
)
from features.api.runtime.chat_execution.preview_contract import (
    build_preview_contract_validation_callback,
)
from features.api.runtime.chat_execution.task_metadata import (
    build_ws_chat_stream_task_metadata_from_prompt_occupancy,
)
from features.api.runtime.chat_prompt_augmentation import (
    request_requires_preview_contract,
)
from features.api.runtime.chat_stream_usage_preview_callback import (
    build_chat_stream_usage_preview_refresh_callback,
)
from features.api.streaming.agentic_sse_generator import (
    create_agentic_sse_stream_generator,
)

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.logging.protocols import TraceLogger
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.openai.usage.models import CanonicalUsage
    from core.runtime.protocols import RequestProtocol
    from core.runtime.request_context import RequestContext
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("create_ws_chat_agent_stream",)


def create_ws_chat_agent_stream(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    runtime: AssistantTimelineRuntime,
    request_json: JSONDict,
    task: Task | None,
    reply_queue: Queue[Event] | None,
    required_capabilities: tuple[str, ...],
    required_modalities: tuple[str, ...],
    prepared_agent_request: PreparedExecutionRequest | None,
    cancel_on_disconnect: bool,
    logger: TraceLogger,
    stream_transcript: OpenAIStreamTranscript,
    first_iteration_cancellation_id: str | None = None,
) -> AsyncGenerator[bytes]:
    async def create_ws_agent_iteration_task(
        payload: JSONDict,
        iteration_context: RequestContext,
        effective_cancellation_id: str,
        _on_bytes: Callable[[bytes], Awaitable[None] | None],
    ) -> tuple[Task, Queue[Event]]:
        prompt_occupancy = await count_prompt_occupancy_async(
            prompt_token_counter=api_context.dependencies.prompt_token_counter,
            request_payload=payload,
            token_estimation_profile=runtime.usage_preview_token_estimation_profile,
        )
        async with runtime.quota_release_lock:
            bundle = await create_streaming_inference_task(
                api_context.dependencies,
                context=iteration_context,
                request_json=payload,
                task_type=(task.task_type if task is not None else TASK_TYPE_CHAT_COMPLETION),
                user_id=runtime.user_id,
                owner_type="conversation",
                owner_id=runtime.conv_id,
                cancellation_id=effective_cancellation_id,
                metadata=build_ws_chat_stream_task_metadata_from_prompt_occupancy(
                    runtime=runtime,
                    prompt_occupancy=prompt_occupancy,
                ),
                request_source=REQUEST_SOURCE_WEBUI_WS,
            )
        return (bundle.task, bundle.reply_queue)

    async def on_iteration_task_ready(task: Task, _iteration_index: int) -> None:
        async with runtime.quota_release_lock:
            runtime.active_task_id = task.task_id
            runtime.clear_quota_reservation()

    async def on_visible_usage_resolved(usage: CanonicalUsage) -> None:
        runtime.canonical_usage = build_internal_usage_payload(usage)

    return create_agentic_sse_stream_generator(
        request=request,
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        context=context,
        task=task,
        initial_reply_queue=reply_queue,
        required_modalities=required_modalities,
        required_capabilities=required_capabilities,
        prepared_agent_request=prepared_agent_request,
        request_source=REQUEST_SOURCE_WEBUI_WS,
        include_usage=True,
        cancel_on_disconnect=cancel_on_disconnect,
        on_compacted_prompt_occupancy=None,
        on_inference_payload_prepared=build_chat_stream_usage_preview_refresh_callback(
            runtime=runtime,
            logger=logger,
            trace_id=context.trace_id,
            turn_id=context.agent_turn_id,
            config=api_context.dependencies.config,
            prompt_token_counter=api_context.dependencies.prompt_token_counter,
            model_resolution_service=api_context.dependencies.model_resolution_service,
            model_information_service=api_context.dependencies.model_information_service,
            model_provider_coordinator=api_context.dependencies.model_provider_coordinator,
            virtual_model_get=api_context.dependencies.model_virtual_model_service.virtual_model_get,
            stream_transcript=stream_transcript,
            model_parameter_service=api_context.dependencies.model_parameter_service,
            plugin_manager=api_context.dependencies.plugin_manager,
            state_aggregator=api_context.dependencies.state_aggregator,
            orchestrator_lifecycle=api_context.dependencies.orchestrator_lifecycle,
            request_context=context,
        ),
        create_iteration_task=create_ws_agent_iteration_task,
        on_visible_usage_resolved=on_visible_usage_resolved,
        on_iteration_task_ready=on_iteration_task_ready,
        validate_visible_assistant_output=build_preview_contract_validation_callback(
            api_dependencies=api_context.dependencies,
            runtime=runtime,
            request_json=request_json,
        ),
        first_iteration_cancellation_id=first_iteration_cancellation_id,
        initial_output_publication_mode=(
            AgentOutputPublicationMode.VALIDATE_BEFORE_PUBLISH
            if request_requires_preview_contract(request_json)
            else AgentOutputPublicationMode.STREAM_LIVE
        ),
        acknowledge_stream_consumption=True,
    )
