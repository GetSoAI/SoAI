"""SoAI - Task orchestration persistence operations [backend/core/tasks/orchestration_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import DatabaseError, StateError, ValidationError
from core.tasks.orchestration_context_cache import merge_orchestration_context_snapshot
from core.tasks.protocols import TaskRegistryProtocol

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.tasks.task import Task

__all__ = (
    "cache_and_persist_orchestration_state",
    "persist_orchestration_state",
    "persist_with_logging",
)

OPERATION_CORE_TASKS_ORCHESTRATION_PERSISTENCE_PERSIST_WITH_LOGGING = (
    "core.tasks.orchestration_persistence.persist_with_logging"
)


async def persist_orchestration_state(registry: TaskRegistryProtocol, task_id: str) -> bool:
    task = await registry.get(task_id)
    if not task or not task.orchestration_context:
        return False
    state_dict = task.orchestration_context.to_persistable_dict()
    persisted = await registry.database_tasks.update_orchestration_state(task_id, state_dict)
    return bool(persisted)


async def persist_with_logging(
    registry: TaskRegistryProtocol,
    task_id: str,
    *,
    logger: LoggerProtocol,
    operation: str,
    trace_id: str | None = None,
) -> tuple[bool, Exception | None]:
    message = f"Failed to persist orchestration state for task [{task_id}]."
    try:
        persisted = await persist_orchestration_state(registry, task_id)
    except (
        DatabaseError,
        ValidationError,
        RuntimeError,
        OSError,
        TypeError,
        ValueError,
    ) as exception:
        log_exception(
            logger,
            exception,
            message=message,
            trace_id=trace_id,
            operation=OPERATION_CORE_TASKS_ORCHESTRATION_PERSISTENCE_PERSIST_WITH_LOGGING,
        )
        return (False, exception)
    if not persisted:
        state_error = StateError(message, operation=operation, details={"task_id": task_id})
        log_exception(
            logger,
            state_error,
            message=message,
            trace_id=trace_id,
            operation=OPERATION_CORE_TASKS_ORCHESTRATION_PERSISTENCE_PERSIST_WITH_LOGGING,
        )
        return (False, state_error)
    return (True, None)


async def cache_and_persist_orchestration_state(
    registry: TaskRegistryProtocol,
    task: Task,
    *,
    logger: LoggerProtocol,
    operation: str,
    trace_id: str | None = None,
) -> tuple[bool, Exception | None]:
    merged_task = await merge_orchestration_context_snapshot(registry, task)
    return await persist_with_logging(
        registry,
        merged_task.task_id,
        logger=logger,
        operation=operation,
        trace_id=trace_id,
    )
