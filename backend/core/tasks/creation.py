"""SoAI - Task creation operations [backend/core/tasks/creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sqlite3
from typing import TYPE_CHECKING

from core.database.mutation_requests import (
    MutationAdmissionDraft,
    MutationAdmissionRequest,
)
from core.database.task_requests import (
    ConversationInteractionCheckpointRequest,
    CreateUnifiedTaskRequest,
)
from core.errors.exceptions import (
    DatabaseError,
    TaskConcurrencyLimitError,
    ValidationError,
)
from core.events.types_base import Event
from core.events.types_tasks import TaskCreatedEvent
from core.logging.trace import get_logger
from core.runtime.request_sources import RequestSource, normalize_request_source
from core.serialization.json import serialize_json_compact_stable
from core.tasks.enums import TaskStatus
from core.tasks.errors import MutationAdmissionConflictError, TaskIDCollisionError
from core.tasks.eviction import cleanup_evicted_events, evict_if_needed
from core.tasks.notifications import publish_event
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from core.tasks.ttl import TTLUseDefault
from core.tasks.type_catalog import (
    TaskTypeId,
    is_orchestrated_inference_task_type,
)
from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.tasks.ttl import TTLMillis
    from core.types.json import JSONDict

__all__ = (
    "create",
    "create_streaming_task",
)

LOGGER_NAME = "SoAI.core.tasks.creation"


async def create(
    registry: TaskRegistryProtocol,
    task_type: TaskTypeId,
    user_id: int,
    owner_id: str,
    owner_type: str,
    *,
    task_id: str | None = None,
    cancellation_id: str,
    status: TaskStatus = TaskStatus.PENDING,
    status_message: str | None = None,
    ttl_ms: TTLMillis = TTLUseDefault,
    poll_interval_ms: int = 1000,
    progress_total: int | None = None,
    metadata: JSONDict | None = None,
    reply_queue: asyncio.Queue[Event] | None = None,
    request_source: RequestSource | None = None,
    delivery_mode: str | None = None,
    mutation_admission: MutationAdmissionDraft | None = None,
    interaction_checkpoint: ConversationInteractionCheckpointRequest | None = None,
) -> Task:
    logger = get_logger(LOGGER_NAME)
    max_concurrent_value = registry.max_concurrent_by_owner_type.get(owner_type)
    max_concurrent = (
        max_concurrent_value
        if is_strict_int(max_concurrent_value)
        else registry.max_concurrent_per_owner
    )
    effective_ttl: int | None
    if ttl_ms is TTLUseDefault:
        effective_ttl = registry.default_ttl_ms
    elif ttl_ms is None:
        effective_ttl = None
    elif isinstance(ttl_ms, int) and (not isinstance(ttl_ms, bool)):
        effective_ttl = ttl_ms
    else:
        raise ValidationError("ttl_ms must be an integer, None, or TTLUseDefault.")
    orchestration_context: OrchestrationContext | None = None
    orchestration_state_json: str | None = None
    if is_orchestrated_inference_task_type(task_type):
        if request_source is None or delivery_mode is None:
            raise ValidationError(
                "Orchestrated inference task creation requires request_source and delivery_mode.",
            )
        normalized_request_source = normalize_request_source(request_source)
        if normalized_request_source is None:
            raise ValidationError("request_source must be a non-empty string.")
        normalized_delivery_mode = delivery_mode.strip()
        if not normalized_delivery_mode:
            raise ValidationError("delivery_mode is required.")
        orchestration_context = OrchestrationContext(
            request_source=normalized_request_source,
            delivery_mode=normalized_delivery_mode,
        )
        orchestration_state_json = serialize_json_compact_stable(
            orchestration_context.to_persistable_dict(),
        )
    elif request_source is not None or delivery_mode is not None:
        raise ValidationError(
            "request_source and delivery_mode are only valid for orchestrated inference task types.",
        )
    task = Task.create(
        task_type=task_type,
        user_id=user_id,
        owner_id=owner_id,
        owner_type=owner_type,
        task_id=task_id,
        cancellation_id=cancellation_id,
        status=status,
        status_message=status_message,
        ttl_ms=effective_ttl,
        poll_interval_ms=poll_interval_ms,
        progress_total=progress_total,
        metadata=metadata,
        reply_queue=reply_queue,
    )
    if is_orchestrated_inference_task_type(task_type):
        if orchestration_state_json is None or orchestration_context is None:
            raise ValidationError("Orchestrated inference task is missing orchestration_state.")
        task = task.with_orchestration_context(orchestration_context)
    task_request = CreateUnifiedTaskRequest(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status.value,
        user_id=task.user_id,
        owner_id=task.owner_id,
        owner_type=task.owner_type,
        ttl_ms=task.ttl_ms,
        poll_interval_ms=task.poll_interval_ms,
        progress_total=task.progress_total,
        metadata=(serialize_json_compact_stable(task.metadata) if task.metadata else None),
        cancellation_id=task.cancellation_id,
        orchestration_state=orchestration_state_json,
        status_message=task.status_message,
        max_concurrent=max_concurrent,
        interaction_checkpoint=interaction_checkpoint,
    )
    created_new = True
    try:
        if mutation_admission is None:
            created = await registry.database_tasks.create_unified_task(task_request)
        else:
            admission = await registry.database_tasks.accept_mutation_task(
                task_request,
                MutationAdmissionRequest(
                    request_id=mutation_admission.request_id,
                    conflict_keys=mutation_admission.conflict_keys,
                    shared_conflict_keys=mutation_admission.shared_conflict_keys,
                    accepted_task_id=task.task_id,
                    operation_type=mutation_admission.operation_type,
                    target_identity=mutation_admission.target_identity,
                    owner_id=task.owner_id,
                    authorization_scope=mutation_admission.authorization_scope,
                    command_payload=mutation_admission.command_payload,
                    schema_discriminator=mutation_admission.schema_discriminator,
                    recovery_payload_encrypted=mutation_admission.recovery_payload_encrypted,
                    excluded_target_names=mutation_admission.excluded_target_names,
                    supersedes_request_id=mutation_admission.supersedes_request_id,
                ),
                server_time_ms=epoch_ms(),
            )
            if admission.outcome == "conflict":
                raise MutationAdmissionConflictError(admission.task_id or None)
            if admission.outcome == "replay":
                existing = await registry.get(task.task_id, force_refresh=True)
                if existing is None:
                    raise DatabaseError(
                        "Replayed mutation task is unavailable.",
                        operation="task_registry.create_mutation_replay",
                    )
                task = (
                    existing.with_reply_queue(reply_queue) if reply_queue is not None else existing
                )
                task = task.with_mutation_admission_outcome("replay")
                created_new = False
            else:
                task = task.with_mutation_admission_outcome("accepted")
            created = True
        if not created:
            existing = await registry.get(task.task_id, force_refresh=True)
            existing_status = existing.status.value if existing else "unknown"
            raise TaskIDCollisionError(task.task_id, existing_status)
    except TaskConcurrencyLimitError:
        raise
    except sqlite3.IntegrityError as exception:
        exc_str = str(exception)
        if "UNIQUE constraint failed" in exc_str or "PRIMARY KEY constraint" in exc_str:
            existing = await registry.get(task.task_id)
            existing_status = existing.status.value if existing else "unknown"
            raise TaskIDCollisionError(task.task_id, existing_status) from exception
        raise DatabaseError(
            f"Database integrity constraint violation: {exception}",
            operation="task_registry.create",
            cause=exception,
        ) from exception
    if reply_queue is not None:
        registry.bind_reply_queue_identity(
            reply_queue,
            task_id=task.task_id,
            user_id=task.user_id,
        )
    async with registry.tasks_lock:
        registry.tasks[task.task_id] = task
        evicted_ids = evict_if_needed(registry)
    if evicted_ids:
        await cleanup_evicted_events(registry, evicted_ids)
    logger.debug(
        "Created task %s (%s) for %s:%s",
        task.task_id,
        task.task_type,
        owner_type,
        owner_id,
    )
    if created_new:
        await publish_event(
            registry.event_bus,
            TaskCreatedEvent(
                task_id=task.task_id,
                task_type=task.task_type,
                owner_id=task.owner_id,
                owner_type=task.owner_type,
                user_id=task.user_id,
                status=task.status.value,
                status_message=task.status_message,
                metadata=task.metadata or {},
                progress_current=task.progress_current,
                progress_total=task.progress_total,
            ),
            "TaskCreatedEvent",
        )
    return task


async def create_streaming_task(
    registry: TaskRegistryProtocol,
    task_type: TaskTypeId,
    user_id: int,
    owner_id: str,
    owner_type: str,
    *,
    task_id: str | None = None,
    cancellation_id: str,
    metadata: JSONDict | None = None,
    ttl_ms: TTLMillis = TTLUseDefault,
    poll_interval_ms: int = 1000,
    progress_total: int | None = None,
    status_message: str | None = None,
    queue_maxsize: int = 1000,
    initial_status: TaskStatus = TaskStatus.PENDING,
    request_source: RequestSource | None = None,
    delivery_mode: str | None = None,
    mutation_admission: MutationAdmissionDraft | None = None,
) -> tuple[Task, asyncio.Queue[Event]]:
    reply_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=queue_maxsize)
    task = await create(
        registry,
        task_type=task_type,
        user_id=user_id,
        owner_id=owner_id,
        owner_type=owner_type,
        task_id=task_id,
        cancellation_id=cancellation_id,
        status=initial_status,
        ttl_ms=ttl_ms,
        poll_interval_ms=poll_interval_ms,
        progress_total=progress_total,
        status_message=status_message,
        metadata=metadata,
        reply_queue=reply_queue,
        request_source=request_source,
        delivery_mode=delivery_mode,
        mutation_admission=mutation_admission,
    )
    return (task, reply_queue)
