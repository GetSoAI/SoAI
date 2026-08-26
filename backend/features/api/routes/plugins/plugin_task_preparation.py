"""SoAI - Plugin route task preparation helpers [backend/features/api/routes/plugins/plugin_task_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.tasks.errors import TaskIDCollisionError
from core.tasks.type_catalog import TaskTypeId
from features.api.runtime.errors import handle_task_id_collision
from features.api.runtime.task_creation_context import (
    create_working_task_from_request_context,
)

if TYPE_CHECKING:
    from fastapi import Request

    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONValue
    from features.api.runtime.context import ApiContext

__all__ = (
    "PreparedPluginTask",
    "prepare_plugin_task_for_request",
)


@dataclass(frozen=True, slots=True)
class PreparedPluginTask:
    registry: TaskRegistryProtocol
    task_id: str
    context: RequestContext
    trace_id: str | None


async def prepare_plugin_task_for_request(
    request: Request,
    *,
    api_context: ApiContext,
    task_type: TaskTypeId,
    status_message: str,
    metadata: dict[str, JSONValue],
) -> PreparedPluginTask:
    context: RequestContext = request.state.context
    try:
        created_task = await create_working_task_from_request_context(
            request=request,
            api_context=api_context,
            task_type=task_type,
            status_message=status_message,
            metadata=dict(metadata),
        )
    except TaskIDCollisionError as exception:
        handle_task_id_collision(request, exception)
    context.task_id = created_task.task.task_id
    return PreparedPluginTask(
        registry=created_task.registry,
        task_id=created_task.task.task_id,
        context=context,
        trace_id=created_task.trace_id,
    )
