"""SoAI - OpenAI streaming upload progress helpers [backend/features/api/routes/openai/streaming_upload_stage_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from features.api.routes.upload_progress_reporting import (
    UploadProgressState,
    emit_upload_progress_update,
)

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol

__all__ = ("UploadProgressReporter",)

LOGGER_NAME_OPENAI_UPLOAD_PROGRESS = "SoAI.features.api.openai_upload_progress"


@dataclass(slots=True)
class UploadProgressReporter:
    registry: TaskRegistryProtocol
    task_id: str
    total_stream_bytes: int | None
    upload_state: UploadProgressState

    async def report(self, bytes_done: int) -> None:
        await emit_upload_progress_update(
            registry=self.registry,
            task_id=self.task_id,
            bytes_done=bytes_done,
            total_bytes=self.total_stream_bytes,
            action="Uploading",
            label="request",
            state=self.upload_state,
            logger=get_logger(LOGGER_NAME_OPENAI_UPLOAD_PROGRESS),
            operation="api_openai.upload.progress",
            progress_start=0,
            progress_end=99,
            keep_current_task_status=True,
        )
