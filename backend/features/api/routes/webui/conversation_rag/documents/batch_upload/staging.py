"""SoAI - WebUI RAG batch upload staging reservations [backend/features/api/routes/webui/conversation_rag/documents/batch_upload/staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.operations import async_remove_if_exists
from core.hardware.protocols_storage import StorageManagerProtocol
from features.api.routes.upload_streaming_reservations import (
    StreamingUploadReservationPurpose,
    StreamingUploadReservationTracker,
)
from features.api.runtime.context import get_request_trace_id
from features.api.runtime.request_cancellation import (
    resolve_request_cancellation_id_or_create,
)

if TYPE_CHECKING:
    from fastapi import Request

    from core.logging.protocols import StandardLogger
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingStagedPart,
    )

__all__ = (
    "build_batch_upload_reservation_tracker",
    "cleanup_batch_upload_staged_part",
    "cleanup_batch_upload_staged_parts",
    "create_batch_upload_declared_total_reporter",
    "resolve_batch_upload_cancellation_id",
)

OPERATION = "webui.conversation_rag.upload_documents_batch.cleanup_part"


def _build_batch_upload_reservation_purpose(
    filename: str,
    resolved_conv_id: str,
) -> StreamingUploadReservationPurpose:
    details = {
        "purpose": "rag_document_batch_upload_temp",
        "filename": filename,
        "conv_id": resolved_conv_id,
    }
    return StreamingUploadReservationPurpose(
        declared_operation="webui.conversation_rag.upload_documents_batch.stage",
        chunk_operation="webui.conversation_rag.upload_documents_batch.stage_chunk",
        declared_details=details,
        chunk_details=details,
    )


def build_batch_upload_reservation_tracker(
    *,
    storage_manager: StorageManagerProtocol,
    temp_dir: str,
    resolved_conv_id: str,
) -> StreamingUploadReservationTracker:
    return StreamingUploadReservationTracker(
        storage_manager=storage_manager,
        temp_dir=temp_dir,
        initial_purpose=_build_batch_upload_reservation_purpose("batch", resolved_conv_id),
        initial_filename="batch",
        purpose_for_filename=lambda filename: _build_batch_upload_reservation_purpose(
            filename,
            resolved_conv_id,
        ),
    )


def create_batch_upload_declared_total_reporter(
    *,
    reservation_tracker: StreamingUploadReservationTracker,
) -> Callable[[int], None]:
    def report_declared_total(declared_total: int) -> None:
        if declared_total <= 0:
            return
        reservation_tracker.reserve_declared_remainder(declared_size=declared_total)

    return report_declared_total


def resolve_batch_upload_cancellation_id(request: Request) -> str:
    return resolve_request_cancellation_id_or_create(
        request,
        subsystem="rag",
        trace_id=get_request_trace_id(request),
        owner="batch_upload",
    )


async def cleanup_batch_upload_staged_part(
    *,
    temp_path: str,
    logger: StandardLogger,
    resolved_conv_id: str,
) -> None:
    try:
        await async_remove_if_exists(temp_path)
    except RECOVERABLE_EXCEPTIONS as cleanup_error:
        log_handled_exception(
            logger,
            cleanup_error,
            message="Failed to cleanup staged batch upload part.",
            operation=OPERATION,
            details={"conv_id": resolved_conv_id, "path": temp_path},
            level="warning",
        )


async def cleanup_batch_upload_staged_parts(
    *,
    files: list[StreamingStagedPart],
    logger: StandardLogger,
    resolved_conv_id: str,
) -> None:
    for part in files:
        await cleanup_batch_upload_staged_part(
            temp_path=part.temp_path,
            logger=logger,
            resolved_conv_id=resolved_conv_id,
        )
