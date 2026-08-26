"""SoAI - Wallpaper upload staging and apply [backend/features/api/routes/webui/wallpaper_upload_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from features.api.routes.upload_streaming_multipart_staged_uploads import (
    SingleStagedUpload,
    stage_single_size_declared_upload,
)
from features.api.routes.upload_streaming_reservations import (
    StreamingUploadReservationTracker,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol, TraceLogger
    from core.tasks.protocols import CancellationTokenScopeCallable
    from core.tasks.task import Task
    from core.wallpaper.settings import WallpaperSettings
    from features.api.routes.upload_streaming_progress import StreamingProgressBridge
    from features.api.runtime.context import ApiContext

__all__ = ("stage_and_apply_wallpaper",)


async def stage_and_apply_wallpaper(
    *,
    request: Request,
    api_context: ApiContext,
    task: Task,
    settings: WallpaperSettings,
    temp_dir: str,
    reservation_tracker: StreamingUploadReservationTracker,
    bridge: StreamingProgressBridge,
    logger_api: LoggerProtocol,
    logger_webui: TraceLogger,
    cancellation_scope: CancellationTokenScopeCallable,
) -> tuple[str | None, int | None, str | None]:
    staged_path: str | None = None
    staged_size: int | None = None
    original_filename: str | None = None

    def on_declared_size(declared_size: int) -> None:
        reservation_tracker.reserve_declared_remainder(declared_size=declared_size)

    def report_file_bytes(bytes_done: int) -> None:
        bridge.report(bytes_done)

    try:
        async with cancellation_scope(
            api_context.dependencies.token_collection,
            api_context.dependencies.cancellation_history,
            api_context.dependencies.cancellation_event_bus,
            cancellation_id=task.cancellation_id,
            owner="wallpaper_upload",
            metadata={},
            logger=logger_api,
        ) as token:
            staged: SingleStagedUpload = await stage_single_size_declared_upload(
                request,
                parser_semaphore=api_context.dependencies.multipart_parser_semaphore,
                temp_dir=temp_dir,
                max_upload_bytes=settings.max_size_bytes,
                token=token,
                report_bytes=report_file_bytes,
                report_stream_bytes=bridge.report,
                on_declared_size=on_declared_size,
                write_controller=reservation_tracker,
                logger=logger_webui,
            )
            staged_path = staged.part.temp_path
            staged_size = staged.part.size_bytes
            original_filename = staged.part.original_filename
            await api_context.dependencies.webui_manager.wallpaper.set_wallpaper_from_staged_file(
                staged_file_path=staged_path,
                original_filename=original_filename,
                content_type=staged.content_type,
                declared_size_bytes=staged.declared_size,
                cancellation_token=token,
            )
            staged_path = None
    finally:
        reservation_tracker.release_active_reservation()
    return staged_path, staged_size, original_filename
