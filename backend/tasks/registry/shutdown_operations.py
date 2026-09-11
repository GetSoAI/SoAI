"""SoAI - Task registry shutdown operations [backend/tasks/registry/shutdown_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_after, deadline_remaining
from core.database.task_requests import UnifiedTaskQueryRequest
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import StandardLogger
from core.logging.trace import get_logger
from core.state.errors import DatabaseUnavailableError
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.timing.constants import EXTENDED_TIMEOUT_SEC
from tasks.registry.conversion import task_from_row

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tasks.task import Task

__all__ = ("shutdown_registry",)

LOGGER_NAME = "SoAI.tasks.registry.shutdown_operations"
OPERATION_TASK_REGISTRY_SHUTDOWN_CLEANUP_TASK = "task_registry.shutdown.cleanup_task"
OPERATION_TASK_REGISTRY_SHUTDOWN_FINALIZE_ACTIVE_TASK = (
    "task_registry.shutdown.finalize_active_task"
)
OPERATION_TASK_REGISTRY_SHUTDOWN_FINALIZE_ACTIVE_TASKS = (
    "task_registry.shutdown.finalize_active_tasks"
)
OPERATION_TASK_REGISTRY_SHUTDOWN_TASK_FROM_ROW = "task_registry.shutdown.task_from_row"


_SHUTDOWN_FINALIZE_BATCH_SIZE = 1000
_SHUTDOWN_FINALIZE_CONCURRENCY = 64


async def _load_active_task_snapshot(
    registry: TaskRegistryLifecycleView,
    *,
    logger: StandardLogger,
    deadline: float,
    transferred_task_ids: frozenset[str] = frozenset(),
) -> tuple[tuple[str, Task | None], ...]:
    tasks: list[tuple[str, Task | None]] = []
    seen_task_ids: set[str] = set()
    offset = 0
    while deadline_remaining(deadline) > 0:
        rows = await registry.database_tasks.query_unified_tasks(
            UnifiedTaskQueryRequest(
                active_only=True,
                limit=_SHUTDOWN_FINALIZE_BATCH_SIZE,
                offset=offset,
            ),
        )
        if not rows:
            break
        page_task_entries: list[tuple[str, Task | None]] = []
        page_has_new_task_ids = False
        for row in rows:
            task_id = row.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                continue
            if task_id in seen_task_ids:
                continue
            seen_task_ids.add(task_id)
            page_has_new_task_ids = True
            if task_id in transferred_task_ids:
                continue
            if await registry.database_tasks.mutation_requires_fenced_finalization(task_id):
                continue
            prefetched_task: Task | None = None
            try:
                prefetched_task = task_from_row(registry.task_catalog, row)
            except KeyError as exception:
                log_exception(
                    logger,
                    exception,
                    message=f"Failed to parse active task row during shutdown: {task_id}",
                    operation=OPERATION_TASK_REGISTRY_SHUTDOWN_TASK_FROM_ROW,
                    level="warning",
                    details={"task_id": task_id},
                )
                prefetched_task = None
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message=f"Failed to parse active task row during shutdown: {task_id}",
                    operation=OPERATION_TASK_REGISTRY_SHUTDOWN_TASK_FROM_ROW,
                    level="warning",
                    details={"task_id": task_id},
                )
                prefetched_task = None
            page_task_entries.append((task_id, prefetched_task))
        if not page_has_new_task_ids:
            break
        tasks.extend(page_task_entries)
        offset += len(rows)
    if deadline_remaining(deadline) <= 0:
        logger.warning(
            "TaskRegistry shutdown reached the %.1fs deadline while reading active task pages.",
            EXTENDED_TIMEOUT_SEC,
        )
    return tuple(tasks)


async def _finalize_active_task(
    registry: TaskRegistryLifecycleView,
    *,
    task_id: str,
    prefetched_task: Task | None,
    logger: StandardLogger,
) -> None:
    shutdown_reason = "Server shutdown"
    try:
        await finalize(
            registry,
            task_id,
            TaskStatus.CANCELLED,
            error_message=shutdown_reason,
            status_message=shutdown_reason,
            prefetched_task=prefetched_task,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to finalize active task {task_id} during shutdown.",
            operation=OPERATION_TASK_REGISTRY_SHUTDOWN_FINALIZE_ACTIVE_TASK,
            level="warning",
        )


async def _finalize_task_batch(
    registry: TaskRegistryLifecycleView,
    *,
    task_entries: tuple[tuple[str, Task | None], ...],
    logger: StandardLogger,
    deadline: float,
) -> None:
    semaphore = asyncio.Semaphore(_SHUTDOWN_FINALIZE_CONCURRENCY)

    async def _run(task_id: str, prefetched_task: Task | None) -> None:
        async with semaphore:
            remaining = deadline_remaining(deadline)
            if remaining <= 0:
                return
            await asyncio.wait_for(
                _finalize_active_task(
                    registry,
                    task_id=task_id,
                    prefetched_task=prefetched_task,
                    logger=logger,
                ),
                timeout=remaining,
            )

    finalize_tasks = [_run(task_id, prefetched_task) for task_id, prefetched_task in task_entries]
    results = await asyncio.gather(*finalize_tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result


async def shutdown_registry(
    registry: TaskRegistryLifecycleView,
    shutdown_event: asyncio.Event,
    cleanup_task: asyncio.Task[None] | None,
    *,
    transferred_task_ids: frozenset[str] = frozenset(),
) -> asyncio.Task[None] | None:
    logger = get_logger(LOGGER_NAME)
    deadline = deadline_after(EXTENDED_TIMEOUT_SEC).deadline_monotonic
    shutdown_event.set()
    try:
        while deadline_remaining(deadline) > 0:
            task_entries = await _load_active_task_snapshot(
                registry,
                logger=logger,
                deadline=deadline,
                transferred_task_ids=transferred_task_ids,
            )
            if not task_entries:
                break
            for batch_start in range(0, len(task_entries), _SHUTDOWN_FINALIZE_BATCH_SIZE):
                if deadline_remaining(deadline) <= 0:
                    break
                await _finalize_task_batch(
                    registry,
                    task_entries=task_entries[
                        batch_start : batch_start + _SHUTDOWN_FINALIZE_BATCH_SIZE
                    ],
                    logger=logger,
                    deadline=deadline,
                )
        else:
            logger.warning(
                "TaskRegistry shutdown reached the %.1fs deadline while finalizing active tasks.",
                EXTENDED_TIMEOUT_SEC,
            )
    except DatabaseUnavailableError:
        logger.debug(
            "TaskRegistry shutdown skipped active task finalization because the database read pool is closed.",
        )
    except TimeoutError:
        logger.warning(
            "TaskRegistry shutdown reached the %.1fs deadline while finalizing active tasks.",
            EXTENDED_TIMEOUT_SEC,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to finalize active tasks during TaskRegistry shutdown.",
            operation=OPERATION_TASK_REGISTRY_SHUTDOWN_FINALIZE_ACTIVE_TASKS,
            level="warning",
        )
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            return None
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="TaskRegistry cleanup loop raised during shutdown (non-critical).",
                operation=OPERATION_TASK_REGISTRY_SHUTDOWN_CLEANUP_TASK,
                level="debug",
            )
            return None
    return cleanup_task
