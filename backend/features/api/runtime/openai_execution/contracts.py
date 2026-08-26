"""SoAI - OpenAI execution admission contracts [backend/features/api/runtime/openai_execution/contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.metrics.protocols import MetricsManagerProtocol
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from core.tasks.task import Task
from core.tasks.type_catalog import TaskTypeId

if TYPE_CHECKING:
    from core.events.types_models_requests import InferenceRequestReceived
    from core.orchestrator.protocols_lifecycle import InferenceDeliveryMode
    from core.types.json import JSONDict
    from features.api.runtime.openai_context.internal_protocols import (
        OpenAIApiContextProtocol,
    )

__all__ = (
    "AcceptedOpenAIExecution",
    "InferenceLifecycleError",
    "InferenceQuotaContext",
    "OpenAIExecutionAdmission",
)


class InferenceLifecycleError(Exception):
    def __init__(self, error_response: JSONResponse) -> None:
        super().__init__(error_response)
        self.error_response: JSONResponse = error_response


@dataclass(frozen=True, slots=True)
class InferenceQuotaContext:
    api_context: OpenAIApiContextProtocol
    key_id: str | None
    reservation: JSONDict | None
    trace_id: str | None
    operation_prefix: str


@dataclass(frozen=True, slots=True)
class OpenAIExecutionAdmission:
    context: RequestContext
    quota: InferenceQuotaContext
    metrics_manager: MetricsManagerProtocol
    task_type: TaskTypeId
    user_id: int
    owner_type: str
    owner_id: str
    cancellation_id: str
    metadata: JSONDict
    payload: JSONDict
    request_event_class: type[InferenceRequestReceived]
    required_capabilities: tuple[str, ...]
    required_modalities: tuple[str, ...]
    request_source: RequestSource
    delivery_mode: InferenceDeliveryMode
    task_id: str | None = None
    reply_queue: asyncio.Queue[Event] | None = None
    attach_reply_queue: bool = True


@dataclass(frozen=True, slots=True)
class AcceptedOpenAIExecution:
    task: Task
    reply_queue: asyncio.Queue[Event] | None
    payload: JSONDict

    def require_reply_queue(self) -> asyncio.Queue[Event]:
        if self.reply_queue is None:
            raise StateError("OpenAI execution admission did not return a reply queue.")
        return self.reply_queue
