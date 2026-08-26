"""SoAI - Shared owned-task wait helper [backend/core/tasks/owned_task_wait.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.errors.exceptions import StateError
from core.tasks.identifiers import normalize_optional_task_id
from core.tasks.protocols import TaskRegistryProtocol

__all__ = ("wait_for_owned_task_snapshot",)


async def wait_for_owned_task_snapshot[OwnedRecordT](
    task_registry: TaskRegistryProtocol,
    *,
    snapshot: OwnedRecordT | None,
    owner_task_id: str | None,
    timeout_ms: int | None,
    can_wait: Callable[[OwnedRecordT], bool],
    reload_snapshot: Callable[[], Awaitable[OwnedRecordT | None]],
) -> OwnedRecordT | None:
    if snapshot is None:
        return None
    if timeout_ms == 0 or not can_wait(snapshot):
        return snapshot
    normalized_owner_task_id = normalize_optional_task_id(owner_task_id)
    if normalized_owner_task_id is None:
        return snapshot
    timeout = None if timeout_ms is None else max(0.0, float(timeout_ms) / 1000.0)
    completed_task = await task_registry.wait_for_completion(
        normalized_owner_task_id,
        timeout=timeout,
    )
    if completed_task is None:
        raise StateError("Owned task is missing while waiting for completion.")
    return await reload_snapshot()
