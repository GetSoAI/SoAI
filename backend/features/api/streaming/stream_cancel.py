"""SoAI - Shared streaming task cancellation helpers [backend/features/api/streaming/stream_cancel.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.runtime.protocols import RequestContextProtocol
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task_cancellation import cancel

__all__ = (
    "safe_cancel_streaming_task",
    "schedule_streaming_task_cancel",
)

OPERATION_FEATURES_API_STREAMING_STREAM_CANCEL_SAFE_CANCEL_STREAMING_TASK = (
    "features.api.streaming.stream_cancel.safe_cancel_streaming_task"
)
OPERATION_FEATURES_API_STREAMING_STREAM_CANCEL_SCHEDULE_STREAMING_TASK_CANCEL = (
    "features.api.streaming.stream_cancel.schedule_streaming_task_cancel"
)


async def safe_cancel_streaming_task(
    registry: TaskRegistryProtocol,
    task_id: str,
    reason: str,
    context: RequestContextProtocol,
    logger: LoggerProtocol,
    operation: str,
) -> None:
    try:
        await cancel(registry, task_id, reason=reason, context=context)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to request task cancellation (non-critical).",
            trace_id=context.trace_id,
            operation=OPERATION_FEATURES_API_STREAMING_STREAM_CANCEL_SAFE_CANCEL_STREAMING_TASK,
            level="debug",
            details={"task_id": task_id, "reason": reason, "operation": operation},
        )


def schedule_streaming_task_cancel(
    registry: TaskRegistryProtocol,
    task_id: str,
    reason: str,
    context: RequestContextProtocol,
    logger: LoggerProtocol,
    operation: str,
    track_background_task: Callable[[asyncio.Task[None]], None],
) -> bool:
    try:
        cancellation_task: asyncio.Task[None] = create_ephemeral_task(
            safe_cancel_streaming_task(registry, task_id, reason, context, logger, operation),
            name=f"stream-cancel-{task_id}",
        )
        track_background_task(cancellation_task)
        return True
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to schedule task cancellation (non-critical).",
            trace_id=context.trace_id,
            operation=OPERATION_FEATURES_API_STREAMING_STREAM_CANCEL_SCHEDULE_STREAMING_TASK_CANCEL,
            level="debug",
            details={"task_id": task_id, "reason": reason},
        )
        return False
