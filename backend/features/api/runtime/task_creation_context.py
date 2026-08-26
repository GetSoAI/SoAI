"""SoAI - Standard task creation from request context [backend/features/api/runtime/task_creation_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.runtime.ownership import resolve_context_ownership
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import (
    TaskTypeId,
    is_orchestrated_inference_task_type,
)
from features.api.runtime.task_registry import require_task_registry_or_raise

if TYPE_CHECKING:
    from fastapi import Request

    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONValue
    from features.api.runtime.context import ApiContext

__all__ = (
    "CreatedWorkingTask",
    "create_working_task_from_request_context",
)


@dataclass(frozen=True, slots=True)
class CreatedWorkingTask:
    registry: TaskRegistryProtocol
    task: Task
    trace_id: str | None


async def create_working_task_from_request_context(
    *,
    request: Request,
    api_context: ApiContext,
    task_type: TaskTypeId,
    status_message: str,
    metadata: dict[str, JSONValue],
    progress_total: int = 100,
) -> CreatedWorkingTask:
    if is_orchestrated_inference_task_type(task_type):
        raise ValidationError(
            "create_working_task_from_request_context does not support orchestrated inference tasks.",
        )
    context = request.state.context
    user_id, owner_id, owner_type, cancellation_id = resolve_context_ownership(context)
    registry = await require_task_registry_or_raise(request, api_context.dependencies)
    task = await create(
        registry,
        task_type=task_type,
        user_id=user_id,
        owner_id=owner_id,
        owner_type=owner_type,
        cancellation_id=cancellation_id,
        status=TaskStatus.WORKING,
        progress_total=progress_total,
        status_message=status_message,
        metadata=metadata,
    )
    trace_id = None
    try:
        trace_id_value = context.trace_id
    except AttributeError:
        trace_id_value = None
    if isinstance(trace_id_value, str) and trace_id_value:
        trace_id = trace_id_value
    return CreatedWorkingTask(
        registry=registry,
        task=task,
        trace_id=trace_id,
    )
