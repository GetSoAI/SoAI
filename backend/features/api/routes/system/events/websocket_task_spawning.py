"""SoAI - Tracked task spawning for WebSocket system events [backend/features/api/routes/system/events/websocket_task_spawning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Coroutine

from core.errors.exceptions import ValidationError
from core.logging.protocols import LoggerProtocol
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

__all__ = ("create_managed_task",)


def create_managed_task(
    coro: Coroutine[None, None, None] | Awaitable[None],
    *,
    name: str,
    logger: LoggerProtocol | None = None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    cancellation_id: str,
    owner: str,
) -> asyncio.Task[None]:
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ValidationError("create_managed_task requires a non-empty name.")
    cancellation_id_value = normalize_cancellation_id(cancellation_id)
    owner_value = str(owner or "").strip()
    if not cancellation_id_value or not owner_value:
        raise ValidationError("create_managed_task requires a non-empty cancellation_id and owner.")
    return spawn_tracked_task(
        coro,
        name=normalized_name,
        logger=logger,
        cancellation_binder=cancellation_binder,
        cancellation_id=cancellation_id_value,
        owner=owner_value,
        finalizer_tracker=finalizer_tracker,
    )
