"""SoAI - Streaming single upload staging [backend/features/api/routes/file_explorer/upload_transfer/streaming/single_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import ValidationError
from core.files.protocols_explorer import (
    FileExplorerCoreProtocol,
    FileSystemRootScopeProtocol,
)
from core.files.upload_staging import cleanup_temp_file
from core.logging.trace import get_logger
from features.api.routes.file_explorer.upload_transfer_destinations import (
    normalize_upload_filename_value,
    resolve_single_destination,
)
from features.api.routes.upload_streaming_multipart_staged_uploads import (
    stage_single_size_declared_upload,
)
from features.api.routes.upload_streaming_reservations import (
    StreamingUploadReservationPurpose,
    StreamingUploadReservationTracker,
)
from features.api.runtime.task_api_errors import raise_invalid_request_error_with_task

if TYPE_CHECKING:
    from fastapi import Request

    from core.concurrency.protocols import CancellationTokenProtocol
    from features.api.routes.file_explorer.upload_transfer_progress_pump import (
        UploadProgressPump,
    )
    from features.api.runtime.context import ApiContext

__all__ = (
    "PreparedSingleUpload",
    "prepare_single_staged_upload",
)

LOGGER_NAME = "SoAI.features.api.single_staging"


@dataclass(frozen=True, slots=True)
class PreparedSingleUpload:
    staged_path: str
    staged_size: int
    safe_filename: str
    virtual_destination: str
    real_destination: str


async def prepare_single_staged_upload(
    request: Request,
    *,
    api_context: ApiContext,
    root_scope: FileSystemRootScopeProtocol,
    file_explorer_core: FileExplorerCoreProtocol,
    base_path: str,
    temp_dir: str,
    task_id: str,
    token: CancellationTokenProtocol,
    progress: UploadProgressPump,
) -> PreparedSingleUpload:
    def report_file_start(filename: str) -> None:
        progress.update_label(filename)

    chunk_reservation_purpose = StreamingUploadReservationPurpose(
        declared_operation="file_explorer.upload.single.stage",
        chunk_operation="file_explorer.upload.single.stage_chunk",
        declared_details={},
        chunk_details={},
    )
    reservation_tracker = StreamingUploadReservationTracker(
        storage_manager=api_context.dependencies.storage_manager,
        temp_dir=temp_dir,
        initial_purpose=chunk_reservation_purpose,
    )

    def on_declared_size(declared_size: int) -> None:
        progress.report(0, total_override=declared_size)
        reservation_tracker.reserve_declared_remainder(declared_size=declared_size)

    def report_file_bytes(bytes_done: int) -> None:
        progress.report(bytes_done)

    try:
        try:
            staged = await stage_single_size_declared_upload(
                request,
                parser_semaphore=api_context.dependencies.multipart_parser_semaphore,
                token=token,
                logger=get_logger(LOGGER_NAME),
                temp_dir=temp_dir,
                max_upload_bytes=None,
                report_bytes=report_file_bytes,
                write_controller=reservation_tracker,
                report_file_start=report_file_start,
                on_declared_size=on_declared_size,
            )
        except ValidationError as exception:
            raise_invalid_request_error_with_task(
                request,
                message=exception.message,
                task_id=task_id,
            )
    finally:
        reservation_tracker.release_active_reservation()
    prepared = False
    try:
        safe_filename = normalize_upload_filename_value(
            request,
            task_id=task_id,
            filename=staged.part.original_filename,
        )
        virtual_destination, real_destination = resolve_single_destination(
            request,
            task_id=task_id,
            root_scope=root_scope,
            file_explorer_core=file_explorer_core,
            base_path=base_path,
            safe_filename=safe_filename,
        )
        result = PreparedSingleUpload(
            staged_path=staged.part.temp_path,
            staged_size=staged.part.size_bytes,
            safe_filename=safe_filename,
            virtual_destination=virtual_destination,
            real_destination=real_destination,
        )
        prepared = True
        return result
    finally:
        if not prepared:
            await uncancel_then_cleanup(cleanup_temp_file(staged.part.temp_path))
