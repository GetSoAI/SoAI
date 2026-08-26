"""SoAI - Agent streaming inference admission helpers [backend/features/agent/runtime/streaming_inference_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.events.types_models_requests import InferenceRequestReceived
from core.openai.inference_normalization import (
    normalize_openai_inference_payload_triple,
)
from core.orchestrator.protocols_lifecycle import InferenceAdmissionRequest
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from core.tasks.type_catalog import TaskTypeId
from core.validation.integers import is_strict_int
from features.agent.runtime.inference_request_payload import (
    resolve_agent_tool_image_relay_request,
)
from features.api.runtime.task_metadata import apply_agent_inference_metadata
from features.openai.reasoning_effort_sanitization import (
    sanitize_reasoning_effort_for_model,
)

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "AgentStreamingTaskBundle",
    "create_streaming_inference_task",
)


@dataclass(frozen=True, slots=True)
class AgentStreamingTaskBundle:
    task: Task
    reply_queue: asyncio.Queue[Event]
    payload: JSONDict
    required_capabilities: tuple[str, ...]
    required_modalities: tuple[str, ...]


def _normalize_payload(
    context: RequestContext,
    request_json: JSONDict,
) -> tuple[JSONDict, tuple[str, ...], tuple[str, ...]]:
    return normalize_openai_inference_payload_triple(
        request_json,
        logger=None,
        trace_id=context.trace_id,
        base_capabilities=(),
        filter_request_fields=True,
    )


def _resolve_reply_queue_maxsize(api_dependencies: ApiDependencies) -> int:
    configured_limit = api_dependencies.config.get_int("SERVER.HTTP.STREAMING.REPLAY_BUFFER_SIZE")
    if is_strict_int(configured_limit) and configured_limit > 0:
        return int(configured_limit)
    return 1000


async def create_streaming_inference_task(
    api_dependencies: ApiDependencies,
    *,
    context: RequestContext,
    request_json: JSONDict,
    task_type: TaskTypeId,
    user_id: int,
    owner_type: str,
    owner_id: str,
    cancellation_id: str,
    metadata: JSONDict,
    request_source: RequestSource,
    reply_queue_maxsize: int | None = None,
) -> AgentStreamingTaskBundle:
    cleaned_request_json, tool_image_relay_requested = resolve_agent_tool_image_relay_request(
        context=context,
        payload=request_json,
    )
    task_metadata = dict(metadata)
    apply_agent_inference_metadata(
        task_metadata,
        tool_image_relay_requested=tool_image_relay_requested,
    )
    normalized_request, required_capabilities, required_modalities = _normalize_payload(
        context,
        cleaned_request_json,
    )
    sanitized_request = normalized_request
    if "reasoning_effort" in normalized_request:
        sanitized_request = await sanitize_reasoning_effort_for_model(
            payload=normalized_request,
            model_resolution_service=api_dependencies.model_resolution_service,
            model_information_service=api_dependencies.model_information_service,
            virtual_model_get=api_dependencies.model_virtual_model_service.virtual_model_get,
        )
    resolved_reply_queue_maxsize = (
        _resolve_reply_queue_maxsize(api_dependencies)
        if reply_queue_maxsize is None
        else int(reply_queue_maxsize)
    )
    receipt = await api_dependencies.orchestrator_control.accept_inference_request(
        InferenceAdmissionRequest(
            request_context=context,
            payload=sanitized_request,
            task_type=task_type,
            user_id=user_id,
            owner_type=owner_type,
            owner_id=owner_id,
            cancellation_id=cancellation_id,
            metadata=task_metadata,
            request_event_class=InferenceRequestReceived,
            required_capabilities=required_capabilities,
            required_modalities=required_modalities,
            request_source=request_source,
            delivery_mode="streaming",
            attach_reply_queue=True,
            reply_queue_maxsize=resolved_reply_queue_maxsize,
        ),
    )
    task = receipt.task
    reply_queue = receipt.reply_queue
    if reply_queue is None:
        raise StateError("Streaming inference admission did not return a reply queue.")
    return AgentStreamingTaskBundle(
        task=task,
        reply_queue=reply_queue,
        payload=sanitized_request,
        required_capabilities=required_capabilities,
        required_modalities=required_modalities,
    )
