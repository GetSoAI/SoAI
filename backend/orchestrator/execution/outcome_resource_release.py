"""SoAI - Terminal outcome capacity release [backend/orchestrator/execution/outcome_resource_release.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.orchestrator.protocols_queue import QueueCycleType

if TYPE_CHECKING:
    from core.tasks.task import Task
    from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("release_terminal_resources",)

LOGGER_NAME = "SoAI.orchestrator.execution.outcome_resource_release"
OPERATION = "orchestrator.outcome.release_terminal_resources"


async def release_terminal_resources(queue: QueueServiceView, task: Task) -> Task:
    logger = get_logger(LOGGER_NAME)
    context = task.orchestration_context
    tracking_id = context.tracking_id if context is not None else task.snapshot_tracking_id
    released_task = task
    try:
        released_task = queue.priority.release_prompt_slot(released_task)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message="Terminal task prompt slot release failed.",
            operation=OPERATION,
            details={"task_id": task.task_id, "resource": "prompt slot"},
            level="warning",
        )
    if tracking_id is not None:
        try:
            await queue.execution_reservations.release(tracking_id)
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=OPERATION)
            log_exception(
                logger,
                coerced,
                message="Terminal task execution reservation release failed.",
                operation=OPERATION,
                details={"task_id": task.task_id, "resource": "execution reservation"},
                level="warning",
            )
    try:
        await queue.tracking.cleanup_completed_task(released_task)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message="Terminal task tracking state release failed.",
            operation=OPERATION,
            details={"task_id": task.task_id, "resource": "tracking state"},
            level="warning",
        )
    try:
        await queue.cycles.close_cycle(released_task, QueueCycleType.PRIORITY)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message="Terminal task priority cycle release failed.",
            operation=OPERATION,
            details={"task_id": task.task_id, "resource": "priority cycle"},
            level="warning",
        )
    return released_task
