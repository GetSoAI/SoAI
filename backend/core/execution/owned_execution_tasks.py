"""SoAI - Shared owned execution task helpers [backend/core/execution/owned_execution_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.execution.protocols import OwnedExecutionSnapshotProtocol
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.owned_task_wait import wait_for_owned_task_snapshot
from core.tasks.status_transitions import update_status
from core.tasks.task_cancellation import request_task_cancellation
from core.tasks.type_catalog import TASK_TYPE_BACKGROUND_JOB

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryLifecycleView, TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "create_owned_execution_task",
    "finalize_owned_execution_task",
    "mark_owned_execution_running",
    "request_owned_execution_cancellation",
    "wait_for_owned_execution_snapshot",
)


def _require_task_status(status: str) -> TaskStatus:
    normalized_status = str(status or "").strip()
    match normalized_status:
        case "queued":
            return TaskStatus.QUEUED
        case "running":
            return TaskStatus.WORKING
        case "completed" | "max_iterations":
            return TaskStatus.COMPLETED
        case "error":
            return TaskStatus.FAILED
        case "cancelled" | "abandoned":
            return TaskStatus.CANCELLED
        case _:
            raise ValidationError(
                f"Unsupported owned execution status: {normalized_status or '<empty>'}.",
            )


async def create_owned_execution_task(
    task_registry: TaskRegistryProtocol,
    *,
    user_id: int,
    owner_id: str,
    owner_type: str,
    cancellation_id: str,
    owner_task_id: str | None,
    initial_status: str,
    status_message: str,
    metadata: JSONDict | None,
) -> Task:
    return await create(
        task_registry,
        task_type=TASK_TYPE_BACKGROUND_JOB,
        user_id=user_id,
        owner_id=owner_id,
        owner_type=owner_type,
        task_id=owner_task_id,
        cancellation_id=cancellation_id,
        status=_require_task_status(initial_status),
        status_message=status_message,
        metadata=metadata,
    )


async def mark_owned_execution_running(
    task_registry: TaskRegistryLifecycleView,
    *,
    owner_task_id: str | None,
    status_message: str,
) -> Task | None:
    if owner_task_id is None or not owner_task_id.strip():
        return None
    return await update_status(
        task_registry,
        owner_task_id.strip(),
        TaskStatus.WORKING,
        status_message=status_message,
    )


async def finalize_owned_execution_task(
    task_registry: TaskRegistryLifecycleView,
    *,
    owner_task_id: str | None,
    final_status: str,
    status_message: str,
    error_message: str | None = None,
    error_code: int | None = None,
    result: dict[str, JSONValue] | None = None,
) -> Task | None:
    if owner_task_id is None or not owner_task_id.strip():
        return None
    return await finalize(
        task_registry,
        owner_task_id.strip(),
        _require_task_status(final_status),
        error_code=error_code,
        error_message=error_message,
        status_message=status_message,
        result=result,
    )


async def request_owned_execution_cancellation(
    task_registry: TaskRegistryLifecycleView,
    *,
    owner_task_id: str | None,
    reason: str,
) -> Task | None:
    if owner_task_id is None or not owner_task_id.strip():
        return None
    return await request_task_cancellation(
        task_registry,
        owner_task_id.strip(),
        reason=reason,
    )


async def wait_for_owned_execution_snapshot[SnapshotT: OwnedExecutionSnapshotProtocol](
    task_registry: TaskRegistryProtocol,
    *,
    snapshot: SnapshotT | None,
    timeout_ms: int | None,
    can_wait: Callable[[SnapshotT], bool],
    reload_snapshot: Callable[[], Awaitable[SnapshotT | None]],
) -> SnapshotT | None:
    owner_task_id = None if snapshot is None else snapshot.owner_task_id
    return await wait_for_owned_task_snapshot(
        task_registry,
        snapshot=snapshot,
        owner_task_id=owner_task_id,
        timeout_ms=timeout_ms,
        can_wait=can_wait,
        reload_snapshot=reload_snapshot,
    )
