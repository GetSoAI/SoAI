"""SoAI - Unexpected accepted inference terminalization [backend/orchestrator/execution/accepted_inference_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from orchestrator.execution.internal_protocols import OutcomeManagerProtocol

__all__ = ("terminalize_unexpected_accepted_inference",)


async def terminalize_unexpected_accepted_inference(
    *,
    task_registry: TaskRegistryProtocol,
    outcomes: OutcomeManagerProtocol,
    task: Task,
    logger: LoggerProtocol,
    operation: str,
) -> bool:
    try:
        current_task = await task_registry.get(task.task_id)
    except HANDLED_RUNTIME_EXCEPTIONS as lookup_exception:
        lookup_error = coerce_to_soai_error(
            lookup_exception,
            operation=operation,
        )
        log_exception(
            logger,
            lookup_error,
            message="Failed to refresh accepted inference before terminalization.",
            operation=operation,
            details={"task_id": task.task_id},
            level="warning",
        )
        current_task = None
    if current_task is not None:
        task = current_task
    if task.status.is_terminal():
        return False
    await outcomes.fail_task(
        task,
        "Internal server error.",
        allow_failover=False,
        error_type=ErrorType.SERVER_ERROR,
    )
    return False
