"""SoAI - OpenAI-compatible binary streaming request orchestration [backend/features/api/streaming/openai_stream_binary_request_handler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping

from fastapi import Request
from pydantic import BaseModel
from starlette.responses import Response

from core.events.types_base import Event
from core.events.types_files import FileContentQuery
from core.events.types_models_requests import TextToSpeechRequestReceived
from core.runtime.ownership import resolve_http_owner_id
from core.runtime.request_source_resolution import resolve_request_source_for_request
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import is_orchestrated_inference_task_type
from core.types.json import JSONValue
from core.users.user_id import coerce_user_id
from features.api.runtime.context import ApiContext
from features.api.runtime.openai_execution.admission import accept_openai_execution
from features.api.runtime.openai_execution.contracts import (
    InferenceLifecycleError,
    InferenceQuotaContext,
    OpenAIExecutionAdmission,
)
from features.api.streaming.openai_stream_binary_request_components import (
    build_streaming_request_event,
    build_streaming_task_metadata,
    coerce_streaming_queue_maxsize,
    normalize_streaming_request_payload,
    resolve_streaming_quota,
)
from features.api.streaming.openai_stream_binary_request_lifecycle import (
    StreamingQuotaReservation,
    create_binary_streaming_task_or_respond,
    publish_request_event_or_respond,
    resolve_streaming_binary_trace_id,
)
from features.api.streaming.openai_stream_binary_response import (
    build_binary_streaming_response,
)
from features.api.streaming.openai_stream_binary_support import resolve_binary_task_type

__all__ = ("handle_streaming_binary_request",)


async def handle_streaming_binary_request(
    request: Request,
    payload: BaseModel | Mapping[str, JSONValue],
    request_event_class: type[TextToSpeechRequestReceived | FileContentQuery],
    media_type: str,
    *,
    api_context: ApiContext,
    base_capabilities: Iterable[str] | None = None,
    base_modalities: Iterable[str] | None = None,
    queue_maxsize: int = 1000,
    stream_format: str | None = None,
    resolved_model_id: str | None = None,
    request_user_id: int | None = None,
    request_api_key_id: str | None = None,
) -> Response:
    context = request.state.context
    trace_id = resolve_streaming_binary_trace_id(request)
    registry = api_context.dependencies.task_registry
    task_type = resolve_binary_task_type(request_event_class)
    payload_dict = normalize_streaming_request_payload(payload)
    model_name = payload_dict.get("model")
    normalized_model_name = model_name if isinstance(model_name, str) else None
    (
        key_id,
        reservation,
        quota_error_response,
        prompt_count,
    ) = await resolve_streaming_quota(
        request,
        api_context,
        task_type=task_type,
        payload_dict=payload_dict,
    )
    if quota_error_response is not None:
        return quota_error_response
    quota = StreamingQuotaReservation(
        api_context=api_context,
        trace_id=trace_id,
        key_id=key_id,
        reservation=reservation,
    )
    quota.apply_to_request_state(request)
    task_metadata = build_streaming_task_metadata(
        context,
        request,
        normalized_model_name,
        request_event_class,
        prompt_count=prompt_count,
    )
    try:
        user_id_value = context.user_id
    except AttributeError:
        user_id_value = None
    normalized_user_id = coerce_user_id(user_id_value)
    owner_id = resolve_http_owner_id(context)
    if is_orchestrated_inference_task_type(task_type):
        try:
            accepted = await accept_openai_execution(
                api_context=api_context,
                admission=OpenAIExecutionAdmission(
                    context=context,
                    quota=InferenceQuotaContext(
                        api_context=api_context,
                        key_id=key_id,
                        reservation=reservation,
                        trace_id=trace_id,
                        operation_prefix="api_streaming.binary",
                    ),
                    metrics_manager=api_context.dependencies.metrics_manager,
                    task_type=task_type,
                    user_id=normalized_user_id,
                    owner_type="http_request",
                    owner_id=owner_id,
                    cancellation_id=context.cancellation_id,
                    metadata=task_metadata,
                    payload=payload_dict,
                    request_event_class=TextToSpeechRequestReceived,
                    required_capabilities=tuple(base_capabilities or ()),
                    required_modalities=tuple(base_modalities or ()),
                    request_source=resolve_request_source_for_request(request),
                    delivery_mode="streaming",
                ),
            )
        except InferenceLifecycleError as lifecycle_error:
            return lifecycle_error.error_response
        task = accepted.task
        reply_queue = accepted.require_reply_queue()
    else:
        initial_status = TaskStatus.WORKING
        progress_total = 100
        reply_queue = asyncio.Queue[Event](maxsize=coerce_streaming_queue_maxsize(queue_maxsize))
        created = await create_binary_streaming_task_or_respond(
            api_context=api_context,
            context=context,
            registry=registry,
            task_type=task_type,
            trace_id=trace_id,
            quota=quota,
            normalized_user_id=normalized_user_id,
            owner_id=owner_id,
            cancellation_id=context.cancellation_id,
            task_metadata=task_metadata,
            initial_status=initial_status,
            progress_total=progress_total,
        )
        if isinstance(created, Response):
            return created
        task = created
        context.task_id = task.task_id
        registry.bind_reply_queue_identity(
            reply_queue,
            task_id=task.task_id,
            user_id=normalized_user_id,
        )
    if not is_orchestrated_inference_task_type(task_type):
        request_event = build_streaming_request_event(
            request_event_class,
            context=context,
            payload_dict=payload_dict,
            reply_queue=reply_queue,
            task_id=task.task_id,
            base_capabilities=base_capabilities,
            base_modalities=base_modalities,
            request_user_id=request_user_id,
            request_api_key_id=request_api_key_id,
        )
        publish_response = await publish_request_event_or_respond(
            api_context=api_context,
            registry=registry,
            task_id=task.task_id,
            request_event=request_event,
            quota=quota,
        )
        if publish_response is not None:
            return publish_response
    return await build_binary_streaming_response(
        api_context=api_context,
        reply_queue=reply_queue,
        context=context,
        trace_id=trace_id,
        task_id=task.task_id,
        request_event_class=request_event_class,
        media_type=media_type,
        stream_format=stream_format,
        resolved_model_id=resolved_model_id,
    )
