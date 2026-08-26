"""SoAI - Initial task acceptance for OpenAI chat requests [backend/features/api/routes/openai/chat/task_acceptance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.events.types_base import Event
from core.events.types_models_requests import InferenceRequestReceived
from core.metrics.protocols import MetricsManagerProtocol
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from core.tasks.task import Task
from features.api.runtime.chat_execution.request_resolution import resolve_task_type
from features.api.runtime.openai_execution.admission import accept_openai_execution
from features.api.runtime.openai_execution.contracts import (
    InferenceQuotaContext,
    OpenAIExecutionAdmission,
)

if TYPE_CHECKING:
    from core.orchestrator.protocols_lifecycle import InferenceDeliveryMode
    from core.types.json import JSONDict
    from features.api.runtime.openai_context.internal_protocols import (
        OpenAIApiContextProtocol,
    )

__all__ = ("accept_chat_inference_task",)


async def accept_chat_inference_task(
    *,
    api_context: OpenAIApiContextProtocol,
    context: RequestContext,
    quota: InferenceQuotaContext,
    metrics_manager: MetricsManagerProtocol,
    request_event_class: type[InferenceRequestReceived],
    user_id: int,
    owner_type: str,
    owner_id: str,
    cancellation_id: str,
    metadata: JSONDict,
    payload: JSONDict,
    required_capabilities: tuple[str, ...],
    required_modalities: tuple[str, ...],
    async_accept_requested: bool,
    is_streaming: bool,
    request_source: RequestSource,
) -> tuple[Task, asyncio.Queue[Event] | None]:
    delivery_mode: InferenceDeliveryMode
    if async_accept_requested:
        delivery_mode = "async"
        attach_reply_queue = False
    elif is_streaming:
        delivery_mode = "streaming"
        attach_reply_queue = True
    else:
        delivery_mode = "blocking"
        attach_reply_queue = True
    accepted = await accept_openai_execution(
        api_context=api_context,
        admission=OpenAIExecutionAdmission(
            context=context,
            quota=quota,
            metrics_manager=metrics_manager,
            task_type=resolve_task_type(request_event_class),
            user_id=user_id,
            owner_type=owner_type,
            owner_id=owner_id,
            cancellation_id=cancellation_id,
            metadata=metadata,
            payload=payload,
            request_event_class=request_event_class,
            required_capabilities=tuple(required_capabilities),
            required_modalities=tuple(required_modalities),
            request_source=request_source,
            delivery_mode=delivery_mode,
            attach_reply_queue=attach_reply_queue,
        ),
    )
    return (accepted.task, accepted.reply_queue)
