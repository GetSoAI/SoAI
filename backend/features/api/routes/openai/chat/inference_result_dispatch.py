"""SoAI - Inference HTTP response dispatch for OpenAI routes [backend/features/api/routes/openai/chat/inference_result_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from starlette.responses import Response

from core.errors.exceptions import StateError
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from features.api.routes.openai.chat.chat_completion_storage import (
    build_storage_context_for_stream,
    store_non_streaming_chat_completion,
)
from features.api.routes.openai.chat.non_streaming.runner import (
    wait_for_non_streaming_inference_result,
)
from features.api.routes.openai.chat.streaming_response import (
    create_inference_streaming_response,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.responses import create_task_accepted_response
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    import asyncio
    from collections.abc import AsyncGenerator, Callable

    from core.events.types_base import Event
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.types.json import JSONDict
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest

__all__ = ("dispatch_openai_inference_response",)


async def dispatch_openai_inference_response(
    *,
    request: Request,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    registry: TaskRegistryProtocol,
    reply_queue: asyncio.Queue[Event] | None,
    context: RequestContext,
    request_json: JSONDict,
    task: Task,
    prepared_agent_request: PreparedExecutionRequest | None,
    required_capabilities: tuple[str, ...],
    required_modalities: tuple[str, ...],
    async_accept_requested: bool,
    is_streaming: bool,
    store_chat_completion: bool,
    stored_request_json: JSONDict,
    api_key_id: str | None,
    request_source: RequestSource,
    stream_transcript: OpenAIStreamTranscript | None = None,
    stream_transform: Callable[[AsyncGenerator[bytes]], AsyncGenerator[bytes]] | None = None,
) -> Response:
    if async_accept_requested:
        response = create_task_accepted_response(
            task_id=task.task_id,
            commit_deadline_ts_ms=None,
            preference_applied="respond-async",
        )
        return response
    if reply_queue is None:
        raise StateError("Inference request reply queue was not attached for non-async response.")
    if is_streaming:
        storage_context = build_storage_context_for_stream(
            api_context=api_context,
            api_key_id=api_key_id,
            task_id=task.task_id,
            request_json=stored_request_json,
            enabled=store_chat_completion,
        )
        return create_inference_streaming_response(
            request,
            api_context,
            stream_dependencies=stream_dependencies,
            reply_queue=reply_queue,
            context=context,
            request_json=request_json,
            task=task,
            prepared_agent_request=prepared_agent_request,
            required_capabilities=required_capabilities,
            required_modalities=required_modalities,
            chat_completion_storage=storage_context,
            request_source=request_source,
            stream_transcript=stream_transcript,
            stream_transform=stream_transform,
        )
    response = await wait_for_non_streaming_inference_result(
        api_context,
        stream_dependencies=stream_dependencies,
        registry=registry,
        task=task,
        reply_queue=reply_queue,
        context=context,
        request_json=request_json,
        required_capabilities=required_capabilities,
    )
    if store_chat_completion:
        storage_error_response = await store_non_streaming_chat_completion(
            api_context=api_context,
            api_key_id=api_key_id,
            task_id=task.task_id,
            request_json=stored_request_json,
            response=response,
        )
        if storage_error_response is not None:
            return storage_error_response
    return response
