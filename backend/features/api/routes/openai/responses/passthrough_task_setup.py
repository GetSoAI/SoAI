"""SoAI - Strict OpenAI Responses task setup and event publishing [backend/features/api/routes/openai/responses/passthrough_task_setup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from core.errors.exceptions import ValidationError
from core.events.types_base import Event
from core.events.types_models_requests import InferenceRequestReceived
from core.models.reference_errors import UnknownModelReferenceError
from core.openai.endpoint_request_contracts import OpenAIEndpointFamily
from core.openai.request_field_filtering import build_inference_request_payload
from core.openai.request_fields import resolve_optional_model_name
from core.runtime.ownership import resolve_http_owner_id
from core.runtime.request_source_resolution import resolve_request_source_for_request
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tasks.type_catalog import TASK_TYPE_OPENAI_RESPONSE
from core.users.user_id import coerce_user_id
from features.api.runtime.context import ApiContext
from features.api.runtime.model_openai_capability_validation import (
    require_openai_capability_for_model,
)
from features.api.runtime.openai_execution.admission import accept_openai_execution
from features.api.runtime.openai_execution.contracts import (
    InferenceLifecycleError,
    InferenceQuotaContext,
    OpenAIExecutionAdmission,
)
from features.api.runtime.openai_quota_reservations import reserve_token_quota_for_task
from features.api.runtime.openai_request_state import apply_openai_api_key_quota_state
from features.api.runtime.openai_request_validation import (
    build_openai_invalid_request_response,
)
from features.api.runtime.task_metadata import (
    apply_openai_prompt_token_count_metadata,
    build_inference_task_metadata,
)

if TYPE_CHECKING:
    from core.orchestrator.protocols_lifecycle import InferenceDeliveryMode
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = (
    "ResponsesTaskSetupResult",
    "setup_responses_inference_task",
)


@dataclass(frozen=True, slots=True)
class ResponsesTaskSetupResult:
    task: Task
    reply_channel: asyncio.Queue[Event]


async def _enforce_responses_capability(
    *,
    api_context: ApiContext,
    model: str,
    required_capabilities: tuple[str, ...],
    trace_id: str,
) -> JSONResponse | None:
    if "responses" not in (required_capabilities or ()):
        return None
    try:
        virtual_model_service = api_context.dependencies.model_virtual_model_service
        await require_openai_capability_for_model(
            model_resolution_service=api_context.dependencies.model_resolution_service,
            model_information_service=api_context.dependencies.model_information_service,
            virtual_model_get=virtual_model_service.virtual_model_get,
            model_name=model,
            capability_key="responses",
            label="",
        )
        return None
    except UnknownModelReferenceError:
        response_message = "Unknown model."
    except ValidationError:
        response_message = "Selected model/provider does not support OpenAI Responses."
    return build_openai_invalid_request_response(
        message=response_message,
        param="model",
        trace_id=trace_id,
    )


async def setup_responses_inference_task(
    *,
    request: Request,
    api_context: ApiContext,
    request_json: JSONDict,
    required_capabilities: tuple[str, ...],
    required_modalities: tuple[str, ...],
    event_type_label: str,
) -> ResponsesTaskSetupResult | JSONResponse:
    context = request.state.context
    metrics_manager = api_context.dependencies.metrics_manager
    try:
        context_user_id = context.user_id
    except AttributeError:
        context_user_id = None
    normalized_user_id = coerce_user_id(context_user_id)
    model = resolve_optional_model_name(request_json)
    if model is not None:
        capability_error = await _enforce_responses_capability(
            api_context=api_context,
            model=model,
            required_capabilities=required_capabilities,
            trace_id=context.trace_id,
        )
        if capability_error is not None:
            return capability_error
    key_id, reservation, quota_error_response, prompt_count = await reserve_token_quota_for_task(
        request,
        api_context,
        request_json,
    )
    if quota_error_response is not None:
        return quota_error_response
    apply_openai_api_key_quota_state(request, key_id=key_id, reservation=reservation)
    task_metadata = build_inference_task_metadata(
        context,
        request,
        model,
        event_type_label,
        endpoint_family=OpenAIEndpointFamily.RESPONSES.value,
    )
    apply_openai_prompt_token_count_metadata(task_metadata, prompt_count=prompt_count)
    try:
        cancellation_id_value = context.cancellation_id
    except AttributeError:
        cancellation_id_value = ""
    cancellation_id = normalize_cancellation_id(cancellation_id_value)
    quota = InferenceQuotaContext(
        api_context=api_context,
        key_id=key_id,
        reservation=reservation,
        trace_id=context.trace_id,
        operation_prefix=f"api_openai.{event_type_label}",
    )
    delivery_mode: InferenceDeliveryMode = (
        "streaming" if request_json.get("stream") is True else "blocking"
    )
    admission = OpenAIExecutionAdmission(
        context=context,
        quota=quota,
        metrics_manager=metrics_manager,
        task_type=TASK_TYPE_OPENAI_RESPONSE,
        user_id=normalized_user_id,
        owner_type="http_request",
        owner_id=resolve_http_owner_id(context),
        cancellation_id=cancellation_id,
        metadata=task_metadata,
        payload=build_inference_request_payload(request_json),
        request_event_class=InferenceRequestReceived,
        required_capabilities=tuple(required_capabilities),
        required_modalities=tuple(required_modalities),
        request_source=resolve_request_source_for_request(request),
        delivery_mode=delivery_mode,
    )
    try:
        accepted = await accept_openai_execution(
            api_context=api_context,
            admission=admission,
        )
    except InferenceLifecycleError as lifecycle_error:
        return lifecycle_error.error_response
    return ResponsesTaskSetupResult(
        task=accepted.task,
        reply_channel=accepted.require_reply_queue(),
    )
