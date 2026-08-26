"""SoAI - Agent inference task creation helpers [backend/features/api/routes/openai/agent_inference_task_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.events.types_base import Event
from core.events.types_models_requests import InferenceRequestReceived
from core.logging.trace import get_logger
from core.openai.inference_normalization import (
    normalize_openai_inference_payload_triple,
)
from core.openai.request_fields import resolve_optional_model_name
from core.openai.token_accounting import PromptOccupancy, count_prompt_occupancy_async
from core.runtime.protocols import RequestProtocol
from core.runtime.request_context import RequestContext
from core.runtime.request_source_resolution import resolve_request_source_for_request
from core.tasks.task import Task
from core.tasks.type_catalog import TaskTypeId
from core.users.user_id import coerce_user_id
from features.agent.runtime.inference_request_payload import (
    resolve_agent_tool_image_relay_request,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_bad_request, raise_from_error_response
from features.api.runtime.openai_execution.admission import accept_openai_execution
from features.api.runtime.openai_execution.contracts import (
    InferenceLifecycleError,
    InferenceQuotaContext,
    OpenAIExecutionAdmission,
)
from features.api.runtime.openai_quota_reservations import reserve_token_quota_for_task
from features.api.runtime.openai_request_state import apply_openai_api_key_quota_state
from features.api.runtime.task_metadata import (
    apply_agent_inference_metadata,
    apply_openai_prompt_token_count_metadata,
    build_inference_task_metadata,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "AgentInferenceTaskBundle",
    "create_agent_inference_task",
)

LOGGER_NAME = "SoAI.features.api.agent_inference_task_creation"


@dataclass(frozen=True, slots=True)
class AgentInferenceTaskBundle:
    task: Task
    reply_queue: asyncio.Queue[Event]
    payload: JSONDict
    required_capabilities: tuple[str, ...]
    required_modalities: tuple[str, ...]


async def _resolve_prompt_count(
    api_context: ApiContext,
    payload: JSONDict,
) -> PromptOccupancy:
    return await count_prompt_occupancy_async(
        prompt_token_counter=api_context.dependencies.prompt_token_counter,
        request_payload=payload,
    )


def _normalize_agent_payload(
    *,
    context: RequestContext,
    payload: JSONDict,
) -> tuple[JSONDict, tuple[str, ...], tuple[str, ...]]:
    return normalize_openai_inference_payload_triple(
        payload,
        logger=get_logger(LOGGER_NAME),
        trace_id=context.trace_id,
        base_capabilities=(),
        filter_request_fields=True,
    )


async def create_agent_inference_task(
    request: RequestProtocol,
    api_context: ApiContext,
    *,
    context: RequestContext,
    payload: JSONDict,
    task_type: TaskTypeId,
    owner_type: str,
    owner_id: str,
    cancellation_id: str,
    event_type_label: str,
) -> AgentInferenceTaskBundle:
    metrics_manager = api_context.dependencies.metrics_manager
    cleaned_payload, tool_image_relay_requested = resolve_agent_tool_image_relay_request(
        context=context,
        payload=payload,
    )
    try:
        normalized_payload, normalized_required_capabilities, normalized_required_modalities = (
            _normalize_agent_payload(
                context=context,
                payload=cleaned_payload,
            )
        )
        prompt_count = await _resolve_prompt_count(api_context, normalized_payload)
    except ValidationError as exception:
        raise_bad_request(request, str(exception))
    model_id = resolve_optional_model_name(normalized_payload)
    key_id, reservation, quota_error_response, _resolved_prompt_count = (
        await reserve_token_quota_for_task(
            request,
            api_context,
            normalized_payload,
            prompt_count=prompt_count,
        )
    )
    if quota_error_response is not None:
        raise_from_error_response(request, quota_error_response)
    apply_openai_api_key_quota_state(request, key_id=key_id, reservation=reservation)
    task_metadata = build_inference_task_metadata(context, request, model_id, event_type_label)
    apply_openai_prompt_token_count_metadata(task_metadata, prompt_count=prompt_count)
    apply_agent_inference_metadata(
        task_metadata,
        tool_image_relay_requested=tool_image_relay_requested,
    )
    try:
        user_id_value = context.user_id
    except AttributeError:
        user_id_value = None
    user_id = coerce_user_id(user_id_value)
    quota = InferenceQuotaContext(
        api_context=api_context,
        key_id=key_id,
        reservation=reservation,
        trace_id=context.trace_id,
        operation_prefix="api_openai.agent_inference",
    )
    try:
        accepted = await accept_openai_execution(
            api_context=api_context,
            admission=OpenAIExecutionAdmission(
                context=context,
                quota=quota,
                metrics_manager=metrics_manager,
                task_type=task_type,
                user_id=user_id,
                owner_type=owner_type,
                owner_id=owner_id,
                cancellation_id=cancellation_id,
                metadata=task_metadata,
                payload=normalized_payload,
                request_event_class=InferenceRequestReceived,
                required_capabilities=normalized_required_capabilities,
                required_modalities=normalized_required_modalities,
                request_source=resolve_request_source_for_request(request),
                delivery_mode="streaming",
            ),
        )
    except InferenceLifecycleError as lifecycle_error:
        raise_from_error_response(request, lifecycle_error.error_response)
    reply_queue = accepted.require_reply_queue()
    return AgentInferenceTaskBundle(
        task=accepted.task,
        reply_queue=reply_queue,
        payload=accepted.payload,
        required_capabilities=normalized_required_capabilities,
        required_modalities=normalized_required_modalities,
    )
