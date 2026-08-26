"""SoAI - Deduplication handling for execution plan decisions [backend/orchestrator/queueing/execution_plan_deduplication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace

from core.events.bus_dispatch_logging import resolve_event_trace_id
from core.logging.protocols import LoggerProtocol
from core.metrics.keyspace_base import DIRECTOR_REQUESTS_DEDUPLICATED
from core.orchestrator.queue_decisions import (
    QueueDecision,
    build_fail_task_decision,
    build_persistence_failed_task_decision,
)
from core.tasks.enums import TaskStatus
from core.tasks.orchestration_persistence import cache_and_persist_orchestration_state
from core.tasks.status_transitions import update_status
from core.tasks.task import Task
from orchestrator.prompt_slot_lifecycle import release_prompt_slot_and_update_cache
from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("apply_execution_plan_deduplication",)


async def apply_execution_plan_deduplication(
    *,
    queue: QueueServiceView,
    task: Task,
    dedup_hash: str | None,
    is_streaming: bool,
    logger: LoggerProtocol,
) -> tuple[Task | None, list[QueueDecision]]:
    registry = queue.task_registry
    if (not queue.deduplication.enabled) or is_streaming:
        await queue.tracking.register_indexed_active_task(task)
        return (task, [])
    await queue.tracking.register_indexed_active_task(task)
    registration = await queue.deduplication.register_or_reuse(
        dedup_hash=dedup_hash or "",
        task_id=task.task_id,
    )
    if not registration.is_waiter:
        return (task, [])
    if not registration.lead_task_id:
        await queue.execution_reservations.release(task.require_orchestration_context().tracking_id)
        await queue.deduplication.remove_waiter(
            dedup_hash=dedup_hash or "",
            task_id=task.task_id,
        )
        return (
            None,
            [
                build_fail_task_decision(
                    task=task,
                    reason="Deduplicated task is missing a lead task reference.",
                    allow_failover=False,
                ),
            ],
        )
    context = replace(
        task.require_orchestration_context(),
        dedup_lead_task_id=registration.lead_task_id,
    )
    task = task.with_orchestration_context(context)
    event = context.event
    persisted, _ = await cache_and_persist_orchestration_state(
        registry,
        task,
        logger=logger,
        operation="orchestrator.queue.apply_execution_plan.persist_dedup_waiter",
        trace_id=resolve_event_trace_id(event) if event is not None else None,
    )
    if not persisted:
        await queue.execution_reservations.release(context.tracking_id)
        await queue.deduplication.remove_waiter(
            dedup_hash=dedup_hash or "",
            task_id=task.task_id,
        )
        return (
            None,
            [build_persistence_failed_task_decision(task)],
        )
    updated_task = await update_status(registry, task.task_id, TaskStatus.DEDUPED)
    if updated_task is None:
        await queue.execution_reservations.release(context.tracking_id)
        await queue.deduplication.remove_waiter(
            dedup_hash=dedup_hash or "",
            task_id=task.task_id,
        )
        refreshed_task = await registry.get(task.task_id, force_refresh=True)
        if refreshed_task is not None:
            task = refreshed_task
        task = await release_prompt_slot_and_update_cache(queue.priority, registry, task)
        if task.status.is_terminal():
            return (None, [])
        return (
            None,
            [build_persistence_failed_task_decision(task)],
        )
    task = updated_task
    await queue.execution_reservations.release(context.tracking_id)
    await queue.tracking.index_task(task)
    logger.debug("Task [%s] deduplicated, waiting for lead result.", task.task_id)
    if queue.orchestrator_deps.metrics is not None:
        queue.orchestrator_deps.metrics.increment_counter(*DIRECTOR_REQUESTS_DEDUPLICATED)
    task = await release_prompt_slot_and_update_cache(queue.priority, registry, task)
    return (None, [])
