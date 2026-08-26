"""SoAI - WebSocket chat stream runtime initialization [backend/features/api/routes/system/events/chat_stream/start_pipeline_initialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import CancelledError, Task
from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.openai.request_field_filtering import build_inference_request_payload
from core.types.json_value import copy_json_dict
from features.api.routes.system.events.chat_stream.start_failure_finalization import (
    finalize_existing_chat_stream_start_failure,
)
from features.api.routes.system.events.chat_stream.start_pipeline_cleanup import (
    cleanup_registered_ws_chat_stream_start_noncritical,
)
from features.api.routes.system.events.websocket_chat_stream.runner import (
    run_ws_chat_stream,
)
from features.api.runtime.chat_stream_usage_preview import (
    refresh_chat_stream_usage_preview_from_inference_payload,
)
from features.api.runtime.knowledge_prompt_delivery import (
    release_knowledge_prompt_claim_noncritical,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.status_preview_state import (
    resolve_latest_user_message_excerpt,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.rag.knowledge_prompt_types import KnowledgePromptDeliveryClaim
    from core.runtime.protocols import RequestProtocol
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies

__all__ = ("initialize_ws_chat_stream_runtime_or_error",)

OPERATION_START_INITIALIZE = "webui_ws_chat_stream.start.initialize"


async def initialize_ws_chat_stream_runtime_or_error(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    chat_streams: MutableMapping[str, AssistantTimelineRuntime],
    request_context: RequestContext,
    tool_context: MCPToolContext | None,
    prepared_agent_request: PreparedExecutionRequest | None,
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None,
    runtime: AssistantTimelineRuntime,
    request_json: JSONDict,
    trace_id: str | None,
    logger: LoggerProtocol,
) -> None:
    placeholder_persisted = runtime.assistant_placeholder_persisted
    failure_finalized = False
    runner_scheduled = False
    scheduled_task: Task[None] | None = None
    chat_streams[runtime.conv_id] = runtime
    try:
        if not placeholder_persisted:
            raise ValidationError(
                "Chat stream initialization requires a persisted assistant placeholder.",
            )
        inference_request_json = (
            copy_json_dict(prepared_agent_request.final_payload)
            if prepared_agent_request is not None
            else build_inference_request_payload(request_json)
        )
        await refresh_chat_stream_usage_preview_from_inference_payload(
            runtime=runtime,
            inference_request_payload=inference_request_json,
            config=api_context.dependencies.config,
            prompt_token_counter=api_context.dependencies.prompt_token_counter,
            model_resolution_service=api_context.dependencies.model_resolution_service,
            model_information_service=api_context.dependencies.model_information_service,
            model_provider_coordinator=api_context.dependencies.model_provider_coordinator,
            virtual_model_get=api_context.dependencies.model_virtual_model_service.virtual_model_get,
            model_parameter_service=api_context.dependencies.model_parameter_service,
            plugin_manager=api_context.dependencies.plugin_manager,
            state_aggregator=api_context.dependencies.state_aggregator,
            orchestrator_lifecycle=api_context.dependencies.orchestrator_lifecycle,
            request_context=request_context,
        )
        runtime.latest_user_message_excerpt = resolve_latest_user_message_excerpt(
            inference_request_json,
        )

        async def run_and_cleanup() -> None:
            try:
                await run_ws_chat_stream(
                    request=request,
                    api_context=api_context,
                    stream_dependencies=stream_dependencies,
                    request_context=request_context,
                    runtime=runtime,
                    request_json=inference_request_json,
                    tool_context=tool_context,
                    prepared_agent_request=prepared_agent_request,
                    knowledge_prompt_claim=knowledge_prompt_claim,
                )
            finally:
                existing = chat_streams.get(runtime.conv_id)
                if existing is runtime:
                    del chat_streams[runtime.conv_id]
                await uncancel_then_cleanup(
                    api_context.dependencies.chat_stream_registry.remove_if_same(runtime),
                )

        scheduled_task = create_ephemeral_task(
            run_and_cleanup(),
            name=f"ws-chat-stream-{runtime.conv_id}",
        )
        runtime.runner_task = scheduled_task
        api_context.dependencies.application_control.track_background_task(scheduled_task)
        runner_scheduled = True
    except CancelledError:
        if scheduled_task is not None:
            scheduled_task.cancel()
            await uncancel_then_cleanup(scheduled_task)
        raise
    except ValidationError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to start WebSocket chat stream due to invalid request data (non-critical).",
            trace_id=trace_id,
            operation=OPERATION_START_INITIALIZE,
            level="debug",
        )
        await finalize_existing_chat_stream_start_failure(
            api_context=api_context,
            stream_dependencies=stream_dependencies,
            runtime=runtime,
            placeholder_persisted=placeholder_persisted,
            error_code="invalid_request_error",
            error_message=str(exception),
        )
        placeholder_persisted = True
        failure_finalized = True
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION_START_INITIALIZE)
        log_exception(
            logger,
            coerced,
            message="Failed to start WebSocket chat stream.",
            trace_id=trace_id,
            operation=OPERATION_START_INITIALIZE,
            level="warning",
            details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
        )
        await finalize_existing_chat_stream_start_failure(
            api_context=api_context,
            stream_dependencies=stream_dependencies,
            runtime=runtime,
            placeholder_persisted=placeholder_persisted,
            error_code=str(coerced.code),
            error_message=str(coerced),
        )
        placeholder_persisted = True
        failure_finalized = True
    finally:
        if not runner_scheduled:
            delete_unfinalized_placeholder = (
                runtime.assistant_placeholder_persisted
                and not failure_finalized
                and not runtime.terminal_persistence_completed
            )
            if scheduled_task is not None:
                scheduled_task.cancel()
                await uncancel_then_cleanup(scheduled_task)
            await uncancel_then_cleanup(
                cleanup_registered_ws_chat_stream_start_noncritical(
                    logger=logger,
                    trace_id=trace_id,
                    api_context=api_context,
                    chat_streams=chat_streams,
                    runtime=runtime,
                    delete_placeholder=delete_unfinalized_placeholder,
                    release_quota=True,
                ),
            )
            await uncancel_then_cleanup(
                release_knowledge_prompt_claim_noncritical(
                    api_dependencies=api_context.dependencies,
                    claim=knowledge_prompt_claim,
                    logger=logger,
                    trace_id=trace_id,
                ),
            )
