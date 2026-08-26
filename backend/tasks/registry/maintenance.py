"""SoAI - Task registry cleanup and maintenance operations [backend/tasks/registry/maintenance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from itertools import islice

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.protocols import StandardLogger
from core.tasks.eviction import cleanup_evicted_events
from core.tasks.protocols import TaskRegistryProtocol
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from tasks.registry.cache_policy import prune_terminal_cache_entries
from tasks.registry.conversation_interaction_expiry import (
    cleanup_expired_conversation_interactions,
)
from tasks.registry.stuck_task_cleanup import cleanup_stuck_tasks

__all__ = (
    "cleanup_expired",
    "prune_terminal_cache",
    "run_cleanup_loop",
)

OPERATION_TASK_REGISTRY_CLEANUP_LOOP = "task_registry.cleanup_loop"
OPERATION_TASK_REGISTRY_CLEANUP_LOOP_CLEANUP_EXPIRED = "task_registry.cleanup_loop.cleanup_expired"
OPERATION_TASK_REGISTRY_CLEANUP_LOOP_CLEANUP_STUCK_TASKS = (
    "task_registry.cleanup_loop.cleanup_stuck_tasks"
)
OPERATION_TASK_REGISTRY_CLEANUP_LOOP_PRUNE_STALE_PROGRESS = (
    "task_registry.cleanup_loop.prune_stale_progress"
)
OPERATION_TASK_REGISTRY_CLEANUP_LOOP_PRUNE_TERMINAL_CACHE = (
    "task_registry.cleanup_loop.prune_terminal_cache"
)
_DEFAULT_STUCK_TASK_EXCLUDE_OWNER_TYPES: tuple[str, ...] = ()
_STUCK_TASK_CHECK_EVERY_ITERATIONS: int = 5


async def cleanup_expired(
    registry: TaskRegistryProtocol,
    batch_size: int = 100,
    *,
    logger: StandardLogger,
) -> int:
    count = await registry.database_tasks.cleanup_expired_unified_tasks()
    if not registry.tasks:
        if count > 0:
            logger.debug("Cleaned up %d expired tasks from DB, 0 from memory", count)
        return count
    expired_ids: list[str] = []
    async with registry.tasks_lock:
        candidate_task_ids = tuple(islice(registry.tasks.keys(), batch_size * 2))
        for tid in candidate_task_ids:
            task = registry.tasks.get(tid)
            if task is None:
                continue
            if task.is_expired():
                registry.tasks.pop(tid, None)
                expired_ids.append(tid)
                if len(expired_ids) >= batch_size:
                    break
    if expired_ids:
        await cleanup_evicted_events(registry, expired_ids)
    if count > 0 or expired_ids:
        logger.debug(
            "Cleaned up %d expired tasks from DB, %d from memory",
            count,
            len(expired_ids),
        )
    return count + len(expired_ids)


async def prune_terminal_cache(registry: TaskRegistryProtocol, batch_size: int = 100) -> int:
    if not registry.terminal_cache:
        return 0
    now = time.monotonic()
    async with registry.tasks_lock:
        removed_ids = prune_terminal_cache_entries(
            registry,
            now=now,
            batch_size=batch_size,
        )
    if removed_ids:
        for task_id in removed_ids:
            await registry.ensure_completion_event(task_id, set_if_terminal=True)
        for task_id in removed_ids:
            await registry.drop_task_lock(task_id)
    return len(removed_ids)


async def run_cleanup_loop(
    registry: TaskRegistryProtocol,
    *,
    logger: StandardLogger,
) -> None:
    consecutive_failures = 0
    max_consecutive_failures = 5
    iteration_counter = 0
    while not registry.shutdown_event.is_set():
        try:
            sleep_interval = max(0.5, float(registry.cleanup_interval_ms) / 1000.0)
            terminal_ttl = max(0.0, float(registry.terminal_cache_ttl))
            if terminal_ttl > 0.0:
                sleep_interval = min(sleep_interval, max(1.0, terminal_ttl / 2.0))
            await asyncio.sleep(sleep_interval)
            if registry.shutdown_event.is_set():
                break
            iteration_counter += 1
            cleanup_error: BaseException | None = None
            prune_error: BaseException | None = None
            progress_prune_error: BaseException | None = None
            stuck_error: BaseException | None = None
            interaction_error: BaseException | None = None
            try:
                await cleanup_expired_conversation_interactions(registry)
            except RECOVERABLE_EXCEPTIONS as exception:
                interaction_error = exception
                log_exception(
                    logger,
                    exception,
                    message="Failed to cleanup expired conversation interactions",
                    operation=OPERATION_TASK_REGISTRY_CLEANUP_LOOP_CLEANUP_EXPIRED,
                    level="warning",
                )
            try:
                await cleanup_expired(registry, logger=logger)
            except RECOVERABLE_EXCEPTIONS as exception:
                cleanup_error = exception
                log_exception(
                    logger,
                    exception,
                    message="Failed to cleanup expired tasks",
                    operation=OPERATION_TASK_REGISTRY_CLEANUP_LOOP_CLEANUP_EXPIRED,
                    level="warning",
                )
            try:
                await prune_terminal_cache(registry)
            except RECOVERABLE_EXCEPTIONS as exception:
                prune_error = exception
                log_exception(
                    logger,
                    exception,
                    message="Failed to prune terminal cache",
                    operation=OPERATION_TASK_REGISTRY_CLEANUP_LOOP_PRUNE_TERMINAL_CACHE,
                    level="warning",
                )
            try:
                pruned_count = registry.prune_stale_terminal_progress()
                if pruned_count > 0:
                    logger.debug(
                        "Pruned %d stale terminal progress state(s)",
                        pruned_count,
                    )
            except RECOVERABLE_EXCEPTIONS as exception:
                progress_prune_error = exception
                log_exception(
                    logger,
                    exception,
                    message="Failed to prune stale terminal progress states",
                    operation=OPERATION_TASK_REGISTRY_CLEANUP_LOOP_PRUNE_STALE_PROGRESS,
                    level="warning",
                )
            if iteration_counter % _STUCK_TASK_CHECK_EVERY_ITERATIONS == 0:
                try:
                    await cleanup_stuck_tasks(
                        registry,
                        exclude_owner_types=_DEFAULT_STUCK_TASK_EXCLUDE_OWNER_TYPES,
                        logger=logger,
                    )
                except RECOVERABLE_EXCEPTIONS as exception:
                    stuck_error = exception
                    log_exception(
                        logger,
                        exception,
                        message="Failed to cleanup stuck tasks",
                        operation=OPERATION_TASK_REGISTRY_CLEANUP_LOOP_CLEANUP_STUCK_TASKS,
                        level="warning",
                    )
                except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
                    stuck_error = exception
                    coerced = coerce_to_soai_error(
                        exception,
                        operation=OPERATION_TASK_REGISTRY_CLEANUP_LOOP_CLEANUP_STUCK_TASKS,
                    )
                    log_exception(
                        logger,
                        coerced,
                        message="Unexpected failure while cleaning up stuck tasks",
                        operation=OPERATION_TASK_REGISTRY_CLEANUP_LOOP_CLEANUP_STUCK_TASKS,
                        level="warning",
                    )
            if (
                cleanup_error
                or prune_error
                or progress_prune_error
                or stuck_error
                or interaction_error
            ):
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logger.warning(
                        "TaskRegistry cleanup loop had %d consecutive failures; pausing briefly.",
                        consecutive_failures,
                    )
                    await asyncio.sleep(RESPONSIVE_TIMEOUT_SEC)
            else:
                consecutive_failures = 0
        except RECOVERABLE_EXCEPTIONS as exception:
            consecutive_failures += 1
            log_exception(
                logger,
                exception,
                message="Unexpected error in task cleanup loop",
                operation=OPERATION_TASK_REGISTRY_CLEANUP_LOOP,
                level="error",
            )
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            consecutive_failures += 1
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_TASK_REGISTRY_CLEANUP_LOOP,
            )
            log_exception(
                logger,
                coerced,
                message="Unexpected fatal error in task cleanup loop",
                operation=OPERATION_TASK_REGISTRY_CLEANUP_LOOP,
                level="error",
            )
