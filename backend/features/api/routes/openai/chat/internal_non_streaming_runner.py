"""SoAI - Internal non-streaming OpenAI chat execution [backend/features/api/routes/openai/chat/internal_non_streaming_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.openai.request_fields import resolve_optional_model_name
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import REQUEST_SOURCE_SYSTEM
from core.serialization.json_parsing import parse_json_value
from core.users.user_id import coerce_user_id
from features.api.routes.openai.chat.non_streaming.runner import (
    wait_for_non_streaming_inference_result,
)
from features.api.routes.openai.chat.task_acceptance import accept_chat_inference_task
from features.api.runtime.chat_execution.request_resolution import resolve_task_owner
from features.api.runtime.openai_execution.contracts import InferenceQuotaContext
from features.api.runtime.response_body import read_response_body_bytes
from features.api.streaming.stream_dependencies import build_stream_dependencies

if TYPE_CHECKING:
    from core.events.types_models_requests import InferenceRequestReceived
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("execute_internal_chat_completion_non_streaming",)


@dataclass(frozen=True, slots=True)
class _InternalApiContext:
    dependencies: ApiDependencies


def _build_internal_task_metadata(
    *,
    trace_id: str,
    model_id: str | None,
    event_type: str,
    source: str,
) -> JSONDict:
    return {
        "trace_id": trace_id,
        "path": f"/internal/{source}",
        "model": model_id,
        "event_type": event_type,
        "internal": True,
        "internal_source": source,
    }


async def execute_internal_chat_completion_non_streaming(
    *,
    api_dependencies: ApiDependencies,
    context: RequestContext,
    request_json: JSONDict,
    request_event_class: type[InferenceRequestReceived],
    required_capabilities: tuple[str, ...] = (),
    required_modalities: tuple[str, ...] = (),
    source: str,
) -> JSONDict:
    stream_value = request_json.get("stream", False)
    if stream_value is True:
        raise ValidationError("Internal chat completion runner does not support streaming.")
    model_id = resolve_optional_model_name(request_json)
    owner_type, owner_id = resolve_task_owner(context, request_json)
    user_id = coerce_user_id(context.user_id)
    quota = InferenceQuotaContext(
        api_context=_InternalApiContext(api_dependencies),
        key_id=None,
        reservation=None,
        trace_id=context.trace_id,
        operation_prefix="internal_openai",
    )
    task_metadata = _build_internal_task_metadata(
        trace_id=context.trace_id,
        model_id=model_id,
        event_type=request_event_class.__name__,
        source=source,
    )
    task, reply_queue = await accept_chat_inference_task(
        api_context=_InternalApiContext(api_dependencies),
        context=context,
        quota=quota,
        metrics_manager=api_dependencies.metrics_manager,
        request_event_class=request_event_class,
        user_id=user_id,
        owner_type=owner_type,
        owner_id=owner_id,
        cancellation_id=context.cancellation_id.strip(),
        metadata=task_metadata,
        payload=dict(request_json),
        required_capabilities=required_capabilities,
        required_modalities=required_modalities,
        async_accept_requested=False,
        is_streaming=False,
        request_source=REQUEST_SOURCE_SYSTEM,
    )
    if reply_queue is None:
        raise StateError("Internal non-streaming execution requires a reply queue.")
    stream_dependencies = build_stream_dependencies(api_dependencies)
    response = await wait_for_non_streaming_inference_result(
        _InternalApiContext(api_dependencies),
        stream_dependencies=stream_dependencies,
        registry=api_dependencies.task_registry,
        task=task,
        reply_queue=reply_queue,
        context=context,
        request_json=request_json,
        required_capabilities=required_capabilities,
    )
    body_bytes = read_response_body_bytes(response)
    if body_bytes is None:
        raise StateError("Internal chat completion returned empty response body.")
    payload = parse_json_value(body_bytes)
    if not isinstance(payload, dict):
        raise StateError("Internal chat completion returned non-object JSON.")
    return dict(payload)
