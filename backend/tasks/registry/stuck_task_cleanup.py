"""SoAI - Task registry stuck task cleanup policy [backend/tasks/registry/stuck_task_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.protocols import StandardLogger
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.type_catalog import (
    TASK_TYPE_RAG_DOCUMENT_UPLOAD,
    TASK_TYPE_RAG_REINDEX,
    TASK_TYPE_RAG_WEB_FETCH_INGEST,
    TaskTypeId,
    is_orchestrated_inference_task_type,
)
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict

__all__ = ("cleanup_stuck_tasks",)

OPERATION_TASK_REGISTRY_CLEANUP_STUCK_TASKS = "task_registry.cleanup_stuck_tasks"
STUCK_TASK_TIMEOUT_MESSAGE = "Task timed out (no activity)"
STUCK_TASK_CANDIDATE_STATUSES = frozenset(
    (
        TaskStatus.PENDING.value,
        TaskStatus.WORKING.value,
        TaskStatus.PROCESSING.value,
    ),
)


def _default_excluded_task_type_values(
    registry: TaskRegistryLifecycleView,
) -> frozenset[str]:
    return frozenset(
        task_type
        for task_type in registry.task_catalog.task_types
        if is_orchestrated_inference_task_type(task_type)
        or task_type
        in (
            TASK_TYPE_RAG_DOCUMENT_UPLOAD,
            TASK_TYPE_RAG_WEB_FETCH_INGEST,
            TASK_TYPE_RAG_REINDEX,
        )
    )


def _filter_stuck_rows(
    rows: list[JSONDict],
    *,
    registry: TaskRegistryLifecycleView,
    exclude_task_types: tuple[TaskTypeId, ...],
) -> list[JSONDict]:
    excluded: frozenset[str]
    if exclude_task_types:
        excluded = frozenset(exclude_task_types)
    else:
        excluded = _default_excluded_task_type_values(registry)
    if not excluded:
        return rows
    return [row for row in rows if row.get("task_type") not in excluded]


async def _finalize_stuck_task(
    registry: TaskRegistryLifecycleView,
    *,
    task_id: str,
    stuck_timeout_ms: int,
    logger: StandardLogger,
) -> bool:
    updated = await finalize(
        registry,
        task_id,
        TaskStatus.FAILED,
        error_code=504,
        error_message=STUCK_TASK_TIMEOUT_MESSAGE,
        status_message=STUCK_TASK_TIMEOUT_MESSAGE,
    )
    if updated is None:
        return False
    logger.info(
        "Marked stuck task %s as failed (no update for %ds)",
        task_id,
        max(0, int(stuck_timeout_ms)) // 1000,
    )
    return True


async def cleanup_stuck_tasks(
    registry: TaskRegistryLifecycleView,
    *,
    exclude_owner_types: tuple[str, ...] = (),
    exclude_task_types: tuple[TaskTypeId, ...] = (),
    limit: int = 1000,
    logger: StandardLogger,
) -> int:
    stuck_timeout_ms = registry.stuck_task_timeout_ms
    if stuck_timeout_ms <= 0:
        return 0
    cutoff_epoch_ms = epoch_ms() - int(stuck_timeout_ms)
    if cutoff_epoch_ms <= 0:
        return 0
    stuck_rows = await registry.database_tasks.query_stuck_active_tasks(
        cutoff_epoch_ms=cutoff_epoch_ms,
        exclude_owner_types=exclude_owner_types,
        limit=limit,
    )
    stuck_rows = _filter_stuck_rows(
        stuck_rows,
        registry=registry,
        exclude_task_types=exclude_task_types,
    )
    finalized = 0
    for row in stuck_rows:
        if row.get("status") not in STUCK_TASK_CANDIDATE_STATUSES:
            continue
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            continue
        try:
            if await _finalize_stuck_task(
                registry,
                task_id=task_id,
                stuck_timeout_ms=stuck_timeout_ms,
                logger=logger,
            ):
                finalized += 1
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=f"Failed to cleanup stuck task {task_id}",
                operation=OPERATION_TASK_REGISTRY_CLEANUP_STUCK_TASKS,
                details={"task_id": task_id},
                level="warning",
            )
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_TASK_REGISTRY_CLEANUP_STUCK_TASKS,
            )
            log_exception(
                logger,
                coerced,
                message=f"Unexpected failure while cleaning up stuck task {task_id}",
                operation=OPERATION_TASK_REGISTRY_CLEANUP_STUCK_TASKS,
                details={"task_id": task_id},
                level="warning",
            )
    if finalized > 0:
        logger.info("Cleaned up %d stuck active tasks", finalized)
    return finalized
