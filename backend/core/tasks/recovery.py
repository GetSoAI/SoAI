"""SoAI - Task registry recovery operations for startup [backend/core/tasks/recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exceptions import SoAIError, StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryLifecycleView
from core.timing.durations import seconds_to_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "StaleTaskReconciliationFailure",
    "StaleTaskReconciliationResult",
    "reconcile_stale_active_tasks_on_startup",
)

OPERATION = "task_registry.reconcile_stale_active_tasks_on_startup"


@dataclass(frozen=True, slots=True)
class StaleTaskReconciliationFailure:
    task_id: str
    error: SoAIError


@dataclass(frozen=True, slots=True)
class StaleTaskReconciliationResult:
    finalized_count: int
    failures: tuple[StaleTaskReconciliationFailure, ...]


async def reconcile_stale_active_tasks_on_startup(
    registry: TaskRegistryLifecycleView,
    *,
    started_at_epoch_ms: int,
    grace_seconds: int = 2,
    exclude_owner_types: tuple[str, ...] = (),
    exclude_task_types: tuple[str, ...] = (),
    exclude_task_ids: tuple[str, ...] = (),
    failure_message: str = "Server restarted",
    limit: int = 20000,
) -> StaleTaskReconciliationResult:
    cutoff_epoch_ms = started_at_epoch_ms - seconds_to_ms(max(0, grace_seconds))
    if cutoff_epoch_ms <= 0:
        return StaleTaskReconciliationResult(
            finalized_count=0,
            failures=(),
        )
    batch_limit = max(1, limit)
    finalized_total = 0
    failures: list[StaleTaskReconciliationFailure] = []
    cursor: tuple[int, str] | None = None
    while True:
        rows = await registry.database_tasks.query_stuck_active_tasks(
            cutoff_epoch_ms=cutoff_epoch_ms,
            exclude_owner_types=exclude_owner_types,
            exclude_task_types=exclude_task_types,
            limit=batch_limit,
            after_updated_at_ms=cursor[0] if cursor is not None else None,
            after_task_id=cursor[1] if cursor is not None else None,
        )
        if not rows:
            return StaleTaskReconciliationResult(
                finalized_count=finalized_total,
                failures=tuple(failures),
            )
        batch_cursors = _validate_batch_cursors(rows, after_cursor=cursor)
        for row in rows:
            task_id_value = row.get("task_id")
            if not isinstance(task_id_value, str) or not task_id_value:
                raise StateError(
                    "Stale task query returned a row without a task identifier.",
                    operation=OPERATION,
                )
            if task_id_value in exclude_task_ids:
                continue
            try:
                updated = await finalize(
                    registry,
                    task_id_value,
                    TaskStatus.FAILED,
                    error_code=503,
                    error_message=failure_message,
                    status_message=failure_message,
                )
                if updated is not None:
                    finalized_total += 1
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                failures.append(
                    StaleTaskReconciliationFailure(
                        task_id=task_id_value,
                        error=coerce_to_soai_error(
                            exception,
                            operation=OPERATION,
                        ),
                    )
                )
        cursor = batch_cursors[-1]
        if len(rows) < batch_limit:
            return StaleTaskReconciliationResult(
                finalized_count=finalized_total,
                failures=tuple(failures),
            )


def _validate_batch_cursors(
    rows: list[JSONDict],
    *,
    after_cursor: tuple[int, str] | None,
) -> tuple[tuple[int, str], ...]:
    cursors: list[tuple[int, str]] = []
    previous_cursor = after_cursor
    for row in rows:
        updated_at_ms = row.get("updated_at_ms")
        task_id = row.get("task_id")
        if (
            isinstance(updated_at_ms, bool)
            or not isinstance(updated_at_ms, int)
            or updated_at_ms < 0
            or not isinstance(task_id, str)
            or not task_id
        ):
            raise StateError(
                "Stale task query returned an invalid keyset cursor.",
                operation=OPERATION,
            )
        cursor = (updated_at_ms, task_id)
        if previous_cursor is not None and cursor <= previous_cursor:
            raise StateError(
                "Stale task query returned a non-increasing keyset cursor.",
                operation=OPERATION,
            )
        cursors.append(cursor)
        previous_cursor = cursor
    return tuple(cursors)
