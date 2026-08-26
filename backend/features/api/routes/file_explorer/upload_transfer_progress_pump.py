"""SoAI - File explorer upload progress pump [backend/features/api/routes/file_explorer/upload_transfer_progress_pump.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.pump_lifecycle import close_pump_task
from core.concurrency.queue_ops import (
    QueueDropTracker,
    log_queue_drop_with_tracker,
    put_nowait_with_overwrite,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.progress.percent import clamp_percent
from core.progress.speed import SpeedCalculator
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.cancellation_ids import normalize_cancellation_id
from features.api.routes.upload_progress_reporting import (
    UploadProgressState,
    emit_upload_progress_update,
)

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TaskRegistryProtocol,
    )

__all__ = ("UploadProgressPump",)

LOGGER_NAME = "SoAI.features.api.upload_transfer_progress_pump"
OPERATION = "api_file_explorer.upload_progress"


_PROGRESS_CLOSE_SENTINEL: tuple[int, int | None] = (-1, None)
_PROGRESS_THROTTLE_SECONDS = 0.25
_PROGRESS_QUEUE_DROP_WARNING_INTERVAL_SECONDS: float = 30.0
UPLOAD_PROGRESS_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = RECOVERABLE_EXCEPTIONS + (
    RuntimeError,
    TypeError,
    AttributeError,
)


class UploadProgressPump:

    def __init__(
        self,
        *,
        task_registry: TaskRegistryProtocol,
        task_id: str,
        action: str,
        label: str,
        total_bytes: int | None,
        cancellation_binder: TaskCancellationBinderProtocol,
        finalizer_tracker: TaskFinalizerTrackerProtocol,
        cancellation_id: str,
        owner: str,
        progress_start: int = 0,
        progress_end: int = 99,
    ) -> None:
        self._logger = get_logger(LOGGER_NAME)
        self._task_registry = task_registry
        self._task_id = task_id
        self._action = action
        self._label = label
        self._total_bytes = total_bytes if total_bytes and total_bytes > 0 else None
        self._cancellation_binder = cancellation_binder
        self._finalizer_tracker = finalizer_tracker
        self._cancellation_id = normalize_cancellation_id(cancellation_id)
        self._owner = str(owner or "").strip()
        self._progress_start = clamp_percent(progress_start)
        self._progress_end = clamp_percent(progress_end)
        self._latest_bytes_done = 0
        self._queue: asyncio.Queue[tuple[int, int | None]] = asyncio.Queue(maxsize=1000)
        self._pump_task: asyncio.Task[None] | None = None
        self._upload_state = UploadProgressState(speed_calculator=SpeedCalculator())
        self._drop_tracker = QueueDropTracker(_PROGRESS_QUEUE_DROP_WARNING_INTERVAL_SECONDS)

    def update_label(self, label: str) -> None:
        self._label = label

    @property
    def latest_bytes_done(self) -> int:
        return self._latest_bytes_done

    def start(self) -> None:
        if self._pump_task is not None:
            return
        self._pump_task = spawn_tracked_task(
            self._run(),
            name=f"file-explorer-upload-progress:{self._task_id}",
            logger=self._logger,
            cancellation_binder=self._cancellation_binder,
            cancellation_id=self._cancellation_id,
            owner=self._owner,
            finalizer_tracker=self._finalizer_tracker,
        )
        self.report(0, total_override=self._total_bytes)

    def report(self, bytes_done: int, *, total_override: int | None = None) -> None:
        normalized_bytes = max(0, int(bytes_done))
        self._latest_bytes_done = normalized_bytes
        normalized_total = total_override if total_override and total_override > 0 else None
        result = put_nowait_with_overwrite(
            self._queue,
            (normalized_bytes, normalized_total),
            overwrite_attempts=1,
        )
        if not result.delivered:
            log_queue_drop_with_tracker(
                self._logger,
                self._drop_tracker,
                max(1, result.dropped_count),
                f"Upload progress queue full for task_id={self._task_id}",
            )

    async def close(self, *, final_bytes_done: int | None = None) -> None:
        if self._pump_task is None:
            return
        if final_bytes_done is not None:
            self.report(final_bytes_done, total_override=self._total_bytes)
        put_nowait_with_overwrite(self._queue, _PROGRESS_CLOSE_SENTINEL, overwrite_attempts=5)
        pump_task = self._pump_task
        self._pump_task = None
        await close_pump_task(
            pump_task,
            timeout_seconds=5.0,
            logger=self._logger,
            timeout_message=f"Upload progress pump close timed out (task_id={self._task_id}).",
        )

    async def _run(self) -> None:
        while True:
            bytes_done, total_override = await self._queue.get()
            try:
                if (bytes_done, total_override) == _PROGRESS_CLOSE_SENTINEL:
                    return
                if total_override is not None and total_override > 0:
                    self._total_bytes = int(total_override)
                await self._handle_progress_update(bytes_done)
            finally:
                self._queue.task_done()

    async def _handle_progress_update(self, bytes_done: int) -> None:
        await emit_upload_progress_update(
            registry=self._task_registry,
            task_id=self._task_id,
            bytes_done=bytes_done,
            total_bytes=self._total_bytes,
            action=self._action,
            label=self._label,
            state=self._upload_state,
            logger=self._logger,
            operation=OPERATION,
            progress_start=self._progress_start,
            progress_end=self._progress_end,
            min_interval_seconds=_PROGRESS_THROTTLE_SECONDS,
            keep_current_task_status=False,
            recoverable_exceptions=UPLOAD_PROGRESS_RECOVERABLE_EXCEPTIONS,
            error_message="Failed to update file explorer upload progress (non-critical).",
        )
