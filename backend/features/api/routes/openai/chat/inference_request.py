"""SoAI - OpenAI chat inference request handling [backend/features/api/routes/openai/chat/inference_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from starlette.responses import Response

from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.protocols import TaskRegistryProtocol
from features.api.routes.openai.chat.agentic_async_dispatch import (
    maybe_execute_async_agentic_request,
)
from features.api.routes.openai.chat.agentic_request_dispatch import (
    maybe_execute_direct_agentic_request,
)
from features.api.routes.openai.chat.inference_request_lifecycle_context import (
    build_inference_request_lifecycle_context,
)
from features.api.routes.openai.chat.inference_result_dispatch import (
    dispatch_openai_inference_response,
)
from features.api.routes.openai.chat.task_acceptance import accept_chat_inference_task
from features.api.runtime.chat_execution.lifecycle import (
    build_prepared_chat_task_metadata,
    build_prepared_inference_payload,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.error_response_fields import (
    extract_error_fields_from_response,
)
from features.api.runtime.openai_execution.contracts import (
    InferenceLifecycleError,
)
from features.api.streaming.stream_dependencies import build_stream_dependencies
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from features.api.runtime.chat_execution.contracts import PreparedChatExecution

__all__ = ("handle_inference_request",)

LOGGER_NAME = "SoAI.features.api.inference_request"


async def handle_inference_request(
    *,
    request: Request,
    api_context: ApiContext,
    prepared_execution: PreparedChatExecution,
    stream_transcript: OpenAIStreamTranscript | None = None,
    stream_transform: Callable[[AsyncGenerator[bytes]], AsyncGenerator[bytes]] | None = None,
) -> Response:
    logger = get_logger(LOGGER_NAME)
    metrics_manager = api_context.dependencies.metrics_manager
    context = prepared_execution.request_context
    tool_context = prepared_execution.tool_context
    prepared_agent_request = prepared_execution.prepared_agent_request
    prepared_agent_turn = prepared_agent_request is not None
    lifecycle_context = build_inference_request_lifecycle_context(
        api_context=api_context,
        request_context=context,
        logger=logger,
        api_key_id=prepared_execution.api_key_id,
        quota_reservation=prepared_execution.quota_reservation,
    )
    try:
        stream_dependencies: StreamDependencies = build_stream_dependencies(
            api_context.dependencies,
        )
        registry: TaskRegistryProtocol = api_context.dependencies.task_registry
        if tool_context is not None:
            context.mcp_tool_context = tool_context
        task_metadata = build_prepared_chat_task_metadata(
            request=request,
            prepared_execution=prepared_execution,
        )
        async_agentic_response = await maybe_execute_async_agentic_request(
            request=request,
            api_context=api_context,
            stream_dependencies=stream_dependencies,
            context=context,
            request_json=prepared_execution.request_json,
            tool_context=tool_context,
            prepared_agent_request=prepared_agent_request,
            request_event_class=prepared_execution.request_event_class,
            async_accept_requested=prepared_execution.async_accept_requested,
            is_streaming=prepared_execution.is_streaming,
            api_key_id=prepared_execution.api_key_id,
            quota_reservation=prepared_execution.quota_reservation,
        )
        if async_agentic_response is not None:
            return async_agentic_response
        direct_agentic_response = await maybe_execute_direct_agentic_request(
            request=request,
            api_context=api_context,
            stream_dependencies=stream_dependencies,
            context=context,
            request_json=prepared_execution.request_json,
            tool_context=tool_context,
            prepared_agent_request=prepared_agent_request,
            prepared_agent_turn=prepared_agent_turn,
            request_event_class=prepared_execution.request_event_class,
            async_accept_requested=prepared_execution.async_accept_requested,
            is_streaming=prepared_execution.is_streaming,
            api_key_id=prepared_execution.api_key_id,
            quota_reservation=prepared_execution.quota_reservation,
        )
        if direct_agentic_response is not None:
            return direct_agentic_response
        inference_request_json = build_prepared_inference_payload(prepared_execution)
        try:
            task, reply_queue = await accept_chat_inference_task(
                api_context=api_context,
                context=context,
                quota=lifecycle_context.quota,
                metrics_manager=metrics_manager,
                request_event_class=prepared_execution.request_event_class,
                user_id=prepared_execution.user_id,
                owner_type=prepared_execution.owner_type,
                owner_id=prepared_execution.owner_id,
                cancellation_id=prepared_execution.cancellation_id,
                metadata=task_metadata,
                payload=inference_request_json,
                required_capabilities=prepared_execution.required_capabilities,
                required_modalities=prepared_execution.required_modalities,
                async_accept_requested=prepared_execution.async_accept_requested,
                is_streaming=prepared_execution.is_streaming,
                request_source=prepared_execution.request_source,
            )
        except InferenceLifecycleError as lifecycle_error:
            error_message, error_type = extract_error_fields_from_response(
                lifecycle_error.error_response,
            )
            if prepared_agent_turn and tool_context is not None:
                await lifecycle_context.finalize_claimed_turn_error(
                    tool_context=tool_context,
                    error_message=error_message,
                    error_type=error_type,
                    operation="api_openai.handle_inference_request.claimed_turn_start_failure",
                    log_message="Failed to finalize claimed agent turn after inference task admission failure (non-critical).",
                )
            return lifecycle_error.error_response
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        await lifecycle_context.handle_failure(
            tool_context=tool_context,
            claimed_agent_turn=prepared_agent_turn,
            exception=exception,
            log_message="Unhandled error while preparing OpenAI inference request (non-critical).",
            level="debug",
            finalize_log_message="Failed to finalize claimed agent turn after OpenAI inference request error (non-critical).",
        )
        raise
    return await dispatch_openai_inference_response(
        request=request,
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        registry=registry,
        reply_queue=reply_queue,
        context=context,
        request_json=prepared_execution.request_json,
        task=task,
        prepared_agent_request=prepared_agent_request,
        required_capabilities=prepared_execution.required_capabilities,
        required_modalities=prepared_execution.required_modalities,
        async_accept_requested=prepared_execution.async_accept_requested,
        is_streaming=prepared_execution.is_streaming,
        store_chat_completion=prepared_execution.storage.store_chat_completion,
        stored_request_json=prepared_execution.storage.stored_request_json,
        api_key_id=prepared_execution.api_key_id,
        request_source=prepared_execution.request_source,
        stream_transcript=stream_transcript,
        stream_transform=stream_transform,
    )
