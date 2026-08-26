"""SoAI - OpenAI chat streaming response wiring [backend/features/api/routes/openai/chat/streaming_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import StreamingResponse

from core.events.types_base import Event
from core.openai.request_features import extract_usage_reporting_requested
from core.openai.request_pipeline import is_openai_text_completions_path
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from core.system_api.request_paths import get_scope_path
from core.tasks.task import Task
from features.api.routes.openai.chat.streaming_storage import (
    ChatCompletionStorageContext,
    wrap_stream_for_chat_completion_storage,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.responses import build_task_operation_headers
from features.api.streaming.agentic_sse_generator import (
    create_agentic_sse_stream_generator,
)
from features.api.streaming.openai_stream_generator.generator import (
    create_stream_generator,
)
from features.api.streaming.sse_responses import create_sse_response
from features.api.streaming.task_quota_metadata import (
    read_task_quota_budget_inputs,
    resolve_request_max_completion_tokens,
)
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.types.json import JSONDict
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest

__all__ = (
    "ChatCompletionStorageContext",
    "create_inference_streaming_response",
)


def create_inference_streaming_response(
    request: Request,
    api_context: ApiContext,
    *,
    stream_dependencies: StreamDependencies,
    reply_queue: asyncio.Queue[Event],
    context: RequestContext,
    request_json: JSONDict,
    task: Task,
    prepared_agent_request: PreparedExecutionRequest | None,
    required_capabilities: tuple[str, ...],
    required_modalities: tuple[str, ...],
    chat_completion_storage: ChatCompletionStorageContext | None = None,
    request_source: RequestSource,
    stream_transcript: OpenAIStreamTranscript | None = None,
    stream_transform: Callable[[AsyncGenerator[bytes]], AsyncGenerator[bytes]] | None = None,
) -> StreamingResponse:
    tool_context: MCPToolContext | None = context.mcp_tool_context
    requested_model = request_json.get("model")
    model_id = requested_model if isinstance(requested_model, str) else None
    include_usage = extract_usage_reporting_requested(request_json)
    stream_object_hint = (
        "text_completion"
        if is_openai_text_completions_path(get_scope_path(request.scope))
        else "chat.completion.chunk"
    )
    stream_gen: AsyncGenerator[bytes]
    if tool_context is None:
        quota_reservation, quota_prompt_tokens, _model_hint = read_task_quota_budget_inputs(task)
        allow_image_events = "images" in (required_capabilities or ())
        stream_gen = create_stream_generator(
            reply_queue,
            stream_dependencies,
            api_context.dependencies,
            context,
            task_id=task.task_id,
            stream_transcript=stream_transcript,
            model=model_id,
            stream_object_hint=stream_object_hint,
            include_usage=include_usage,
            quota_reservation=quota_reservation,
            quota_prompt_tokens=quota_prompt_tokens,
            max_completion_tokens=resolve_request_max_completion_tokens(request_json),
            allow_image_events=allow_image_events,
            emit_done_marker=stream_transform is None,
            schedule_tool_calls=stream_transform is None,
        )
    else:
        cancel_on_disconnect = api_context.dependencies.config.get_bool(
            "MODELS.ROUTING.CANCEL_ON_CLIENT_DISCONNECT",
        )
        stream_gen = create_agentic_sse_stream_generator(
            request,
            api_context,
            stream_dependencies,
            context,
            task,
            reply_queue,
            required_capabilities,
            required_modalities,
            prepared_agent_request,
            request_source=request_source,
            include_usage=include_usage,
            cancel_on_disconnect=cancel_on_disconnect,
        )
    if chat_completion_storage is not None:
        stream_gen = wrap_stream_for_chat_completion_storage(
            stream_gen,
            storage=chat_completion_storage,
        )
    if stream_transform is not None:
        stream_gen = stream_transform(stream_gen)
    return create_sse_response(
        stream_gen,
        additional_headers=build_task_operation_headers(
            task_id=task.task_id,
            operation_id=context.trace_id,
        ),
    )
