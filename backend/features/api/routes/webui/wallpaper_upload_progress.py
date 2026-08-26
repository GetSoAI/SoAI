"""SoAI - Wallpaper upload progress reporting [backend/features/api/routes/webui/wallpaper_upload_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.progress.speed import SpeedCalculator
from features.api.routes.upload_progress_reporting import (
    UploadProgressState,
    emit_upload_progress_update,
)

__all__ = (
    "WallpaperUploadProgressState",
    "report_wallpaper_upload_progress",
)

LOGGER_NAME = "SoAI.features.api.wallpaper_upload_progress"
OPERATION = "api_theme.upload_wallpaper.progress"

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import TaskRegistryLifecycleView


@dataclass(slots=True)
class WallpaperUploadProgressState:
    upload_state: UploadProgressState

    @classmethod
    def create(cls) -> WallpaperUploadProgressState:
        return WallpaperUploadProgressState(
            upload_state=UploadProgressState(speed_calculator=SpeedCalculator()),
        )


async def report_wallpaper_upload_progress(
    *,
    context: RequestContext,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    bytes_done: int,
    declared_total: int | None,
    state: WallpaperUploadProgressState,
) -> None:
    _ = context
    resolved_total = declared_total if declared_total is not None and declared_total > 0 else None
    await emit_upload_progress_update(
        registry=registry,
        task_id=task_id,
        bytes_done=bytes_done,
        total_bytes=resolved_total,
        action="Uploading",
        label="wallpaper",
        state=state.upload_state,
        logger=get_logger(LOGGER_NAME),
        operation=OPERATION,
        progress_start=0,
        progress_end=99,
    )
