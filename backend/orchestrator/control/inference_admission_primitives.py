"""SoAI - Durable inference admission request primitives [backend/orchestrator/control/inference_admission_primitives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.events.types_base import Event
from core.models.model_info_fields import coerce_plugin_name
from core.models.reference_validation import validate_active_model_reference
from core.runtime.request_context import RequestContext
from orchestrator.control.inference_request_primitives import (
    serialize_request_context_payload,
)

if TYPE_CHECKING:
    from core.events.types_models_requests import InferenceRequestReceived
    from core.orchestrator.protocols_lifecycle import InferenceAdmissionRequest
    from core.types.json import JSONValue
    from orchestrator.control.internal_protocols import (
        OrchestratorControlInferenceAdmissionProtocol,
    )

__all__ = (
    "build_inference_event",
    "build_inference_task_request_context",
    "resolve_plugin_name",
    "resolve_reply_queue",
    "serialize_request_context",
    "serialize_request_context_payload",
    "validate_model_reference",
)


def build_inference_task_request_context(
    *,
    inbound: RequestContext,
    task_id: str,
    cancellation_id: str,
    user_id: int,
) -> RequestContext:
    return RequestContext(
        trace_id=inbound.trace_id,
        client_ip=inbound.client_ip,
        user_id=int(user_id),
        task_id=task_id,
        cancellation_id=cancellation_id,
        mcp_tool_context=inbound.mcp_tool_context,
        agent_mode=inbound.agent_mode,
        agent_turn_id=inbound.agent_turn_id,
        agent_turn_execution_token=inbound.agent_turn_execution_token,
        agent_workspace_path=inbound.agent_workspace_path,
    )


def resolve_reply_queue(request: InferenceAdmissionRequest) -> asyncio.Queue[Event] | None:
    if request.reply_queue is not None:
        return request.reply_queue
    if not request.attach_reply_queue:
        return None
    return asyncio.Queue(maxsize=max(1, int(request.reply_queue_maxsize)))


def build_inference_event(
    *,
    request: InferenceAdmissionRequest,
    request_context: RequestContext,
    task_id: str,
    reply_queue: asyncio.Queue[Event] | None,
) -> InferenceRequestReceived:
    event_queue = reply_queue if reply_queue is not None else asyncio.Queue[Event](maxsize=1)
    return request.request_event_class(
        context=request_context,
        payload=dict(request.payload),
        reply_channel=event_queue,
        task_id=task_id,
        required_capabilities=tuple(request.required_capabilities),
        required_modalities=tuple(request.required_modalities),
    )


def serialize_request_context(context: RequestContext) -> dict[str, JSONValue]:
    return serialize_request_context_payload(context)


async def validate_model_reference(
    control: OrchestratorControlInferenceAdmissionProtocol,
    model_name: str,
) -> tuple[set[str], str | None]:
    virtual_model_map = await control.lifecycle.startup.get_virtual_model_map()
    validated = await validate_active_model_reference(
        model_name=model_name,
        model_resolution_service=control.deps.model_resolution_service,
        model_information_service=control.deps.model_information_service,
        virtual_model_get=virtual_model_map.get,
        unknown_message=f"Unknown model '{model_name}'.",
        disabled_message=f"Model '{model_name}' is disabled.",
        details={"param": "model"},
    )
    if validated.is_virtual:
        return ({validated.routing_key}, None)
    return (set(), validated.routing_key)


async def resolve_plugin_name(
    control: OrchestratorControlInferenceAdmissionProtocol,
    universal_id: str | None,
) -> str | None:
    if universal_id is None:
        return None
    model_info = await control.deps.model_information_service.model_get_info(universal_id)
    return coerce_plugin_name(model_info if isinstance(model_info, dict) else None)
