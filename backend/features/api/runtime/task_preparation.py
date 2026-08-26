"""SoAI - Task metadata building and creation for API commands [backend/features/api/runtime/task_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import Request

from core.database.mutation_requests import MutationAdmissionDraft
from core.events.types_base import Event
from core.runtime.ownership import resolve_http_owner_id
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from core.tasks.creation import create_streaming_task
from core.tasks.enums import TaskStatus
from core.tasks.errors import TaskIDCollisionError
from core.tasks.identifiers import normalize_optional_task_id
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from core.tasks.type_catalog import is_orchestrated_inference_task_type
from core.users.user_id import coerce_user_id
from features.api.runtime.context import resolve_api_context
from features.api.runtime.errors import handle_task_id_collision

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "create_dispatch_task",
    "extract_normalized_task_id",
)


def extract_normalized_task_id(context: RequestContext | None) -> str | None:
    if context is None:
        return None
    return normalize_optional_task_id(context.task_id)


async def create_dispatch_task(
    request: Request,
    registry: TaskRegistryProtocol,
    command_type: type[Event],
    task_metadata: JSONDict,
    *,
    request_source: RequestSource,
    delivery_mode: str,
    mutation_admission: MutationAdmissionDraft | None = None,
) -> tuple[Task, asyncio.Queue[Event]]:
    context = request.state.context
    api_context = resolve_api_context(request)
    user_id = coerce_user_id(context.user_id)
    owner_id = resolve_http_owner_id(context)
    normalized_task_id = extract_normalized_task_id(context)
    task_type = api_context.dependencies.task_type_routing_service.get_task_type_for_command(
        command_type,
    )
    is_orchestrated_inference = is_orchestrated_inference_task_type(task_type)
    initial_status = TaskStatus.QUEUED if is_orchestrated_inference else TaskStatus.WORKING
    progress_total = None if is_orchestrated_inference else 100
    try:
        task, reply_queue = await create_streaming_task(
            registry,
            task_type=task_type,
            user_id=user_id,
            owner_id=owner_id,
            owner_type="http_request",
            task_id=normalized_task_id,
            cancellation_id=context.cancellation_id,
            initial_status=initial_status,
            progress_total=progress_total,
            metadata=task_metadata,
            request_source=(request_source if is_orchestrated_inference else None),
            delivery_mode=(delivery_mode if is_orchestrated_inference else None),
            mutation_admission=mutation_admission,
        )
    except TaskIDCollisionError as exception:
        handle_task_id_collision(request, exception)
    context.task_id = task.task_id
    return task, reply_queue
