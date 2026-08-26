"""SoAI - Orchestrator tracked task creation helpers [backend/orchestrator/execution/task_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.tasks.asyncio_task_spawner import spawn_tracked_task

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.types.json import JSONDict

__all__ = (
    "create_linked_task",
    "create_managed_task",
)


def create_linked_task(
    awaitable: Awaitable[bool],
    *,
    cancellation_binder: TaskCancellationBinderProtocol,
    cancellation_id: str,
    owner: str,
    name: str,
    logger: LoggerProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    metadata: JSONDict | None = None,
    owner_observes_result: bool = False,
) -> asyncio.Task[bool]:
    task = spawn_tracked_task(
        awaitable,
        cancellation_binder=cancellation_binder,
        cancellation_id=cancellation_id,
        owner=owner,
        name=name,
        logger=logger,
        metadata=metadata,
        finalizer_tracker=finalizer_tracker,
        owner_observes_result=owner_observes_result,
    )
    return task


def create_managed_task(
    awaitable: Awaitable[tuple[bool, str] | None],
    *,
    name: str,
    logger: LoggerProtocol | None = None,
    cancellation_binder: TaskCancellationBinderProtocol,
    cancellation_id: str,
    owner: str,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    metadata: JSONDict | None = None,
) -> asyncio.Task[tuple[bool, str] | None]:
    return spawn_tracked_task(
        awaitable,
        cancellation_binder=cancellation_binder,
        cancellation_id=cancellation_id,
        owner=owner,
        name=name,
        logger=logger,
        metadata=metadata,
        finalizer_tracker=finalizer_tracker,
    )
