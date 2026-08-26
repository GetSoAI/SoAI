"""SoAI - Streaming batch upload staging [backend/features/api/routes/file_explorer/upload_transfer/streaming/batch_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import ValidationError
from core.files.upload_errors import MissingRequiredUploadMetadataError
from core.files.upload_staging import cleanup_temp_files
from core.logging.trace import get_logger
from features.api.routes.upload_streaming_multipart_staged_uploads import (
    stage_batch_relative_paths_sizes_upload,
)
from features.api.routes.upload_streaming_reservations import (
    StreamingUploadReservationPurpose,
    StreamingUploadReservationTracker,
)
from features.api.runtime.task_api_errors import raise_api_error_with_task

if TYPE_CHECKING:
    from fastapi import Request

    from core.concurrency.protocols import CancellationTokenProtocol
    from features.api.routes.file_explorer.upload_transfer_progress_pump import (
        UploadProgressPump,
    )
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingMultipartResult,
    )
    from features.api.runtime.context import ApiContext

__all__ = ("stage_streaming_batch_upload",)

LOGGER_NAME = "SoAI.features.api.batch_staging"


async def stage_streaming_batch_upload(
    request: Request,
    *,
    api_context: ApiContext,
    temp_dir: str,
    token: CancellationTokenProtocol,
    progress: UploadProgressPump,
    task_id: str,
) -> tuple[StreamingMultipartResult, list[str], list[int]]:
    chunk_reservation_purpose = StreamingUploadReservationPurpose(
        declared_operation="file_explorer.upload_batch.stage",
        chunk_operation="file_explorer.upload_batch.stage_chunk",
        declared_details={},
        chunk_details={},
    )
    reservation_tracker = StreamingUploadReservationTracker(
        storage_manager=api_context.dependencies.storage_manager,
        temp_dir=temp_dir,
        initial_purpose=chunk_reservation_purpose,
    )
    file_start_count = 0

    def report_file_start(filename: str) -> None:
        nonlocal file_start_count
        file_start_count += 1
        progress.update_label(f"{filename} ({file_start_count})")

    def on_declared_total(total: int) -> None:
        progress.report(0, total_override=total)
        reservation_tracker.reserve_declared_remainder(declared_size=total)

    def report_bytes(bytes_done: int) -> None:
        progress.report(bytes_done)

    try:
        try:
            staged = await stage_batch_relative_paths_sizes_upload(
                request,
                parser_semaphore=api_context.dependencies.multipart_parser_semaphore,
                temp_dir=temp_dir,
                max_upload_bytes=None,
                token=token,
                report_bytes=report_bytes,
                report_file_start=report_file_start,
                on_declared_total=on_declared_total,
                write_controller=reservation_tracker,
                logger=get_logger(LOGGER_NAME),
            )
        except ValidationError as exception:
            message = exception.message
            if isinstance(exception, MissingRequiredUploadMetadataError):
                message = "Missing required batch metadata fields."
            raise_api_error_with_task(
                request,
                422,
                "invalid_request_error",
                message,
                task_id=task_id,
            )
    finally:
        reservation_tracker.release_active_reservation()
    prepared = False
    try:
        relative_sizes: list[int] = []
        for size in staged.relative_sizes:
            if size is None:
                raise_api_error_with_task(
                    request,
                    422,
                    "invalid_request_error",
                    "relative_sizes must contain integers for every file.",
                    task_id=task_id,
                )
            relative_sizes.append(size)
        result = staged.parsed, staged.relative_paths, relative_sizes
        prepared = True
        return result
    finally:
        if not prepared:
            await uncancel_then_cleanup(
                cleanup_temp_files(staged_part.temp_path for staged_part in staged.parsed.files)
            )
