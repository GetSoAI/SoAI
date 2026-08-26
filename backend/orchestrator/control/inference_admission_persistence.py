"""SoAI - Durable inference admission persistence and side-effects [backend/orchestrator/control/inference_admission_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.database.task_requests import (
    CreateDurableInferenceTaskRequest,
    CreateUnifiedTaskRequest,
    DurableQueueItemRequest,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_tasks import TaskCreatedEvent
from core.logging.trace import get_logger
from core.serialization.json import serialize_json_compact_stable
from core.tasks.task import Task
from core.timing.epoch import epoch_ms
from core.validation.epoch import require_unix_epoch_ms

if TYPE_CHECKING:
    from core.events.types_base import Event
    from orchestrator.control.internal_protocols import (
        OrchestratorControlInferenceAdmissionProtocol,
    )

__all__ = (
    "build_task_created_event",
    "persist_admission",
    "run_admission_side_effects",
)

LOGGER_NAME = "SoAI.orchestrator.control.inference_admission_persistence"
OPERATION_BIND_REPLY_QUEUE = "orchestrator.control.accept_inference_request.bind_reply_queue"
OPERATION_UPDATE_TASK_CACHE = "orchestrator.control.accept_inference_request.update_task_cache"


async def persist_admission(
    control: OrchestratorControlInferenceAdmissionProtocol,
    task: Task,
) -> None:
    context = task.require_orchestration_context()
    routing_key = str(context.routing_key or "").strip()
    if not routing_key:
        raise StateError("Task orchestration context is missing routing_key.")
    if context.request_source is None:
        raise StateError("Task orchestration context is missing request_source.")
    delivery_mode = str(context.delivery_mode or "").strip()
    if not delivery_mode:
        raise StateError("Task orchestration context is missing delivery_mode.")
    state_json = serialize_json_compact_stable(context.to_persistable_dict())
    require_unix_epoch_ms(
        round(context.priority_assignment.queued_at * 1000.0),
        error_message="Task queue time must be a valid epoch-millisecond integer.",
    )
    priority_order_at_ms = require_unix_epoch_ms(
        round(context.priority_assignment.priority_order * 1000.0),
        error_message="Task priority order must be a valid epoch-millisecond integer.",
    )
    await control.task_registry.database_tasks.accept_durable_inference_task(
        CreateDurableInferenceTaskRequest(
            task=_build_durable_task_request(task, state_json),
            queue_item=DurableQueueItemRequest(
                task_id=task.task_id,
                phase="ready",
                routing_key=routing_key,
                request_source=context.request_source,
                delivery_mode=delivery_mode,
                request_priority=context.priority_assignment.priority,
                priority_order_at_ms=priority_order_at_ms,
                plugin_name=context.plugin_name,
                available_at_ms=epoch_ms(),
                dedup_hash=context.dedup_hash,
                dedup_lead_task_id=context.dedup_lead_task_id,
            ),
        ),
    )


async def run_admission_side_effects(
    control: OrchestratorControlInferenceAdmissionProtocol,
    task: Task,
    reply_queue: asyncio.Queue[Event] | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if reply_queue is not None:
        try:
            control.task_registry.bind_reply_queue_identity(
                reply_queue,
                task_id=task.task_id,
                user_id=task.user_id,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Durable inference admission could not bind reply queue identity.",
                operation=OPERATION_BIND_REPLY_QUEUE,
                details={"task_id": task.task_id},
                level="warning",
            )
    try:
        await control.task_registry.update_task_cache(task)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Durable inference admission could not update task cache.",
            operation=OPERATION_UPDATE_TASK_CACHE,
            details={"task_id": task.task_id},
            level="warning",
        )


def build_task_created_event(task: Task) -> TaskCreatedEvent:
    return TaskCreatedEvent(
        task_id=task.task_id,
        task_type=task.task_type,
        user_id=task.user_id,
        owner_id=task.owner_id,
        owner_type=task.owner_type,
        status=task.status.value,
        metadata=task.metadata or {},
        status_message=task.status_message,
        progress_current=task.progress_current,
        progress_total=task.progress_total,
    )


def _build_durable_task_request(task: Task, state_json: str) -> CreateUnifiedTaskRequest:
    serialized_metadata = serialize_json_compact_stable(task.metadata) if task.metadata else None
    return CreateUnifiedTaskRequest(
        task_id=task.task_id,
        task_type=task.task_type,
        user_id=task.user_id,
        owner_id=task.owner_id,
        owner_type=task.owner_type,
        status=task.status.value,
        ttl_ms=task.ttl_ms,
        poll_interval_ms=task.poll_interval_ms,
        progress_total=task.progress_total,
        metadata=serialized_metadata,
        cancellation_id=task.cancellation_id,
        orchestration_state=state_json,
        status_message=task.status_message,
        max_concurrent=None,
    )
