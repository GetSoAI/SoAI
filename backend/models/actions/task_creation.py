"""SoAI - Model action task creation [backend/models/actions/task_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.events.types_base import Event
from core.runtime.ownership import resolve_context_ownership
from core.runtime.protocols import RequestOwnershipContextProtocol
from core.tasks.creation import create, create_streaming_task
from core.tasks.enums import TaskStatus
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.type_catalog import TASK_TYPE_BACKGROUND_JOB

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = (
    "ModelActionTaskOwnership",
    "create_reply_bound_model_action_task",
    "create_streaming_model_action_task",
)


@dataclass(frozen=True, slots=True)
class ModelActionTaskOwnership:
    user_id: int
    owner_id: str
    owner_type: str
    cancellation_id: str


def _resolve_model_action_ownership(
    context: RequestOwnershipContextProtocol | None,
) -> ModelActionTaskOwnership:
    user_id, owner_id, owner_type, cancellation_id = resolve_context_ownership(context)
    return ModelActionTaskOwnership(
        user_id=user_id,
        owner_id=owner_id,
        owner_type=owner_type,
        cancellation_id=cancellation_id,
    )


async def create_reply_bound_model_action_task(
    task_registry: TaskRegistryProtocol,
    reply_queue: asyncio.Queue[Event],
    context: RequestOwnershipContextProtocol | None,
    metadata: JSONDict,
) -> str | None:
    if task_registry.resolve_task_identity_for_reply_queue(reply_queue) is not None:
        return None
    ownership = _resolve_model_action_ownership(context)
    await create(
        task_registry,
        task_type=TASK_TYPE_BACKGROUND_JOB,
        user_id=ownership.user_id,
        owner_id=ownership.owner_id,
        owner_type=ownership.owner_type,
        cancellation_id=ownership.cancellation_id,
        status=TaskStatus.WORKING,
        progress_total=100,
        metadata=metadata,
        reply_queue=reply_queue,
    )
    return ownership.cancellation_id


async def create_streaming_model_action_task(
    task_registry: TaskRegistryProtocol,
    context: RequestOwnershipContextProtocol | None,
    metadata: JSONDict,
) -> tuple[Task, asyncio.Queue[Event], ModelActionTaskOwnership]:
    ownership = _resolve_model_action_ownership(context)
    task, reply_queue = await create_streaming_task(
        task_registry,
        task_type=TASK_TYPE_BACKGROUND_JOB,
        user_id=ownership.user_id,
        owner_id=ownership.owner_id,
        owner_type=ownership.owner_type,
        cancellation_id=ownership.cancellation_id,
        initial_status=TaskStatus.WORKING,
        progress_total=100,
        metadata=metadata,
    )
    return task, reply_queue, ownership
