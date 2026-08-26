"""SoAI - Generic upload progress bridge for streaming ingestion [backend/features/api/routes/upload_streaming_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.pump_lifecycle import close_pump_task
from core.concurrency.queue_ops import (
    QueueDropTracker,
    log_queue_drop_with_tracker,
    put_nowait_with_overwrite,
)
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import StandardLogger
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.cancellation_ids import normalize_cancellation_id
from features.api.routes.internal_protocols import MultipartBytesReporter

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = ("StreamingProgressBridge", "build_ignore_multipart_bytes_reporter")

OPERATION_FEATURES_API_ROUTES_UPLOAD_STREAMING_PROGRESS_RUN = (
    "features.api.routes.upload_streaming_progress.run"
)


_PROGRESS_SENTINEL = -1
_PROGRESS_QUEUE_DROP_WARNING_INTERVAL_SECONDS: float = 30.0


class _IgnoreMultipartBytesReporter:
    def __call__(self, bytes_done: int) -> None:
        _ = bytes_done


def build_ignore_multipart_bytes_reporter() -> MultipartBytesReporter:
    return _IgnoreMultipartBytesReporter()


class StreamingProgressBridge:

    def __init__(
        self,
        *,
        callback: Callable[[int], Awaitable[None]],
        logger: StandardLogger,
        operation: str,
        cancellation_binder: TaskCancellationBinderProtocol,
        finalizer_tracker: TaskFinalizerTrackerProtocol,
        cancellation_id: str,
        owner: str,
    ) -> None:
        self._logger = logger
        self._callback = callback
        self._operation = operation
        self._cancellation_binder = cancellation_binder
        self._finalizer_tracker = finalizer_tracker
        self._cancellation_id = normalize_cancellation_id(cancellation_id)
        self._owner = str(owner or "").strip()
        self._queue: asyncio.Queue[int] = asyncio.Queue(maxsize=1000)
        self._task: asyncio.Task[None] | None = None
        self._drop_tracker = QueueDropTracker(_PROGRESS_QUEUE_DROP_WARNING_INTERVAL_SECONDS)

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = spawn_tracked_task(
            self._run(),
            name="upload-streaming-progress",
            logger=self._logger,
            cancellation_binder=self._cancellation_binder,
            cancellation_id=self._cancellation_id,
            owner=self._owner,
            finalizer_tracker=self._finalizer_tracker,
        )

    def report(self, bytes_done: int) -> None:
        result = put_nowait_with_overwrite(
            self._queue,
            max(0, int(bytes_done)),
            overwrite_attempts=1,
        )
        if not result.delivered:
            log_queue_drop_with_tracker(
                self._logger,
                self._drop_tracker,
                max(1, result.dropped_count),
                "Upload progress queue full",
            )

    async def close(self, *, final_bytes_done: int | None = None) -> None:
        if self._task is None:
            return
        if final_bytes_done is not None:
            self.report(final_bytes_done)
        put_nowait_with_overwrite(self._queue, _PROGRESS_SENTINEL, overwrite_attempts=5)
        task = self._task
        self._task = None
        await close_pump_task(
            task,
            timeout_seconds=5.0,
            logger=self._logger,
            timeout_message="Upload progress pump close timed out.",
        )

    async def _run(self) -> None:
        while True:
            bytes_done = await self._queue.get()
            try:
                if bytes_done == _PROGRESS_SENTINEL:
                    return
                try:
                    await self._callback(bytes_done)
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        self._logger,
                        exception,
                        message="Failed to emit streaming upload progress (non-critical).",
                        operation=OPERATION_FEATURES_API_ROUTES_UPLOAD_STREAMING_PROGRESS_RUN,
                        level="debug",
                    )
            finally:
                self._queue.task_done()
