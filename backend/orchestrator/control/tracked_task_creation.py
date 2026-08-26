"""SoAI - Orchestrator control tracked background task creation [backend/orchestrator/control/tracked_task_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.tasks.protocols import SpawnTrackedTaskCallable
from core.tasks.task_cancellation_ops import generate_system_cancellation_id

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.types.json import JSONDict

__all__ = ("create_tracked_background_task",)

LOGGER_NAME = "SoAI.orchestrator.control.tracked_task_creation"


def create_tracked_background_task(
    *,
    coro: Coroutine[None, None, None],
    owner: str,
    metadata: JSONDict | None,
    cancellation_id: str | None,
    name: str | None,
    spawn_tracked_task: SpawnTrackedTaskCallable,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
) -> asyncio.Task[None]:
    logger = get_logger(LOGGER_NAME)
    resolved_cancellation_id = str(
        cancellation_id or "",
    ).strip() or generate_system_cancellation_id(owner)
    return spawn_tracked_task(
        coro,
        owner=owner,
        logger=logger,
        metadata=metadata,
        cancellation_id=resolved_cancellation_id,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        name=name,
    )
