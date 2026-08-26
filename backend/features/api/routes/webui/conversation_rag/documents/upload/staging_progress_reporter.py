"""SoAI - RAG document upload staging progress reporter [backend/features/api/routes/webui/conversation_rag/documents/upload/staging_progress_reporter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.protocols import StandardLogger
from core.progress.speed import SpeedCalculator
from features.api.routes.upload_progress_reporting import (
    UploadProgressState,
    emit_upload_progress_update,
)
from features.api.routes.upload_streaming_reservations import StreamingUploadReservationTracker

__all__ = ("RagDocumentStagingProgressReporter",)

OPERATION = "webui.conversation_rag.upload_document.progress"

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryLifecycleView


class RagDocumentStagingProgressReporter:

    def __init__(
        self,
        *,
        registry: TaskRegistryLifecycleView,
        task_id: str,
        logger: StandardLogger,
        speed_calculator: SpeedCalculator,
        reservation_tracker: StreamingUploadReservationTracker,
    ) -> None:
        self._registry = registry
        self._task_id = task_id
        self._logger = logger
        self._upload_state = UploadProgressState(speed_calculator=speed_calculator)
        self._reservation_tracker = reservation_tracker

    async def report(self, bytes_done: int) -> None:
        declared_size = self._reservation_tracker.declared_size
        await emit_upload_progress_update(
            registry=self._registry,
            task_id=self._task_id,
            bytes_done=bytes_done,
            total_bytes=declared_size,
            action="Uploading",
            label=self._reservation_tracker.current_filename or "document",
            state=self._upload_state,
            logger=self._logger,
            operation=OPERATION,
            progress_start=0,
            progress_end=4,
        )
