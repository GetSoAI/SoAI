"""SoAI - Orchestrator waiter failure helpers [backend/orchestrator/execution/waiter_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from core.tasks.task import Task
from orchestrator.execution.internal_protocols import (
    CancelTaskCallable,
    FailTaskCallable,
)

__all__ = (
    "cancel_waiters_for_routing_key",
    "fail_waiters_for_routing_key",
)

LOGGER_NAME = "SoAI.orchestrator.execution.waiter_failures"
OPERATION = "orchestrator_executor.fail_waiters"


async def cancel_waiters_for_routing_key(
    *,
    routing_key: str,
    reason: str,
    error_type: ErrorType,
    unregister_pending_queue: Callable[[str], Awaitable[deque[Task]]],
    cancel_task: CancelTaskCallable,
) -> None:
    logger = get_logger(LOGGER_NAME)
    tasks = await _pop_waiter_tasks(routing_key, unregister_pending_queue)
    if not tasks:
        return
    logger.info(
        "Cancelling %s waiters for [%s]. Reason: %s",
        len(tasks),
        routing_key,
        reason,
    )
    cancel_tasks = [cancel_task(task, reason=reason, error_type=error_type) for task in tasks]
    gather_results = await asyncio.gather(*cancel_tasks, return_exceptions=True)
    _log_waiter_terminal_errors(
        tasks=tasks,
        results=gather_results,
        routing_key=routing_key,
        action="cancel",
    )


async def fail_waiters_for_routing_key(
    *,
    routing_key: str,
    reason: str,
    allow_failover: bool,
    error_type: ErrorType,
    unregister_pending_queue: Callable[[str], Awaitable[deque[Task]]],
    fail_task: FailTaskCallable,
) -> None:
    logger = get_logger(LOGGER_NAME)
    tasks = await _pop_waiter_tasks(routing_key, unregister_pending_queue)
    if not tasks:
        return
    logger.info(
        "Failing %s waiters for [%s]. Reason: %s",
        len(tasks),
        routing_key,
        reason,
    )
    fail_tasks = [
        fail_task(task, reason=reason, allow_failover=allow_failover, error_type=error_type)
        for task in tasks
    ]
    gather_results = await asyncio.gather(*fail_tasks, return_exceptions=True)
    _log_waiter_terminal_errors(
        tasks=tasks,
        results=gather_results,
        routing_key=routing_key,
        action="fail",
    )


async def _pop_waiter_tasks(
    routing_key: str,
    unregister_pending_queue: Callable[[str], Awaitable[deque[Task]]],
) -> list[Task]:
    waiters_iter = await unregister_pending_queue(routing_key)
    waiters = list(waiters_iter) if waiters_iter is not None else []
    return [waiter for waiter in waiters if isinstance(waiter, Task)]


def _log_waiter_terminal_errors(
    *,
    tasks: list[Task],
    results: list[BaseException | None],
    routing_key: str,
    action: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    for index, gather_result in enumerate(results):
        if isinstance(gather_result, BaseException):
            task_id = tasks[index].task_id
            log_exception(
                logger,
                gather_result,
                message=f"Failed to {action} waiter [{task_id}] for [{routing_key}]",
                operation=OPERATION,
                details={"task_id": task_id, "routing_key": routing_key},
                level="warning",
            )
