"""SoAI - Fenced inference timeout ownership [backend/core/tasks/execution_timeout_claim.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import replace

from core.errors.payload import ErrorPublicPayload
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.orchestration_context import ExecutionTimeoutClaim
from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.task import Task
from core.tasks.task_lock_control import load_task_with_drop_control, task_lock_control
from core.tasks.task_state_merge import merge_task_state

__all__ = (
    "adopt_execution_timeout_delivery",
    "claim_execution_timeout",
    "settle_execution_timeout_delivery",
)

LOGGER_NAME = "SoAI.core.tasks.execution_timeout_claim"


async def claim_execution_timeout(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    public_error: ErrorPublicPayload,
) -> bool:
    async with task_lock_control(registry, task_id) as lock_control:
        task = await load_task_with_drop_control(registry, lock_control, task_id)
        if task is None or task.status.is_terminal():
            return False
        context = task.orchestration_context
        if context is None or context.delivery_in_progress:
            return False
        if (
            task.cancellation_requested_at_ms is not None
            or await registry.cancellation_history.is_cancelled(task.cancellation_id)
        ):
            return False
        claim = ExecutionTimeoutClaim(public_error, context.delivery_version + 1)
        task = task.with_orchestration_context(
            replace(
                context,
                execution_timeout_claim=claim,
                delivery_in_progress=True,
                delivery_version=claim.delivery_version,
            )
        )
        await registry.update_task_cache(task)
    persisted = await finalize(
        registry,
        task_id,
        TaskStatus.FAILED,
        error_code=public_error.http_status,
        error_type=str(public_error.code),
        error_message=public_error.message,
        public_error=public_error,
        emit_reply_completion_event=False,
        delivery_version=claim.delivery_version,
    )
    if persisted is None or persisted.status != TaskStatus.FAILED:
        return False
    async with task_lock_control(registry, task_id):
        retained_task = merge_task_state(cached=task, incoming=persisted)
        if retained_task.orchestration_context is not None:
            retained_task = retained_task.with_orchestration_context(
                retained_task.orchestration_context
            )
        await registry.update_task_cache(retained_task)
        get_logger(LOGGER_NAME).debug(
            "Timeout terminal claim retained. task_id=%s delivery_version=%d reply_queue_attached=%s",
            task_id,
            claim.delivery_version,
            retained_task.reply_queue is not None,
        )
    return True


async def adopt_execution_timeout_delivery(
    registry: TaskRegistryLifecycleView,
    task_id: str,
) -> tuple[Task | None, int | None]:
    async with task_lock_control(registry, task_id):
        task = await registry.get(task_id)
        context = task.orchestration_context if task is not None else None
        claim = context.execution_timeout_claim if context is not None else None
        if task is None or context is None or claim is None or claim.delivery_started:
            return (task, None)
        task = task.with_orchestration_context(
            replace(context, execution_timeout_claim=replace(claim, delivery_started=True))
        )
        await registry.update_task_cache(task)
        get_logger(LOGGER_NAME).debug(
            "Timeout terminal delivery adopted. task_id=%s delivery_version=%d reply_queue_attached=%s",
            task_id,
            claim.delivery_version,
            task.reply_queue is not None,
        )
        return (task, claim.delivery_version)


async def settle_execution_timeout_delivery(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    delivery_version: int,
) -> None:
    async with task_lock_control(registry, task_id):
        async with registry.tasks_lock:
            entry = registry.terminal_cache.get(task_id)
            if entry is None:
                return
            task, _cached_at = entry
            context = task.orchestration_context
            claim = context.execution_timeout_claim if context is not None else None
            if (
                claim is not None
                and claim.delivery_started
                and claim.delivery_version == delivery_version
            ):
                registry.terminal_cache[task_id] = (task.snapshot(), time.monotonic())
