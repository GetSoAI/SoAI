"""SoAI - RAG document multipart staging [backend/features/api/routes/webui/conversation_rag/documents/staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from features.api.routes.upload_streaming_multipart_staged_uploads import (
    stage_single_size_declared_upload,
)
from features.api.routes.upload_streaming_reservations import (
    StreamingUploadReservationPurpose,
    StreamingUploadReservationTracker,
)

if TYPE_CHECKING:
    from fastapi import Request

    from core.concurrency.protocols import CancellationTokenProtocol
    from features.api.routes.upload_streaming_progress import StreamingProgressBridge
    from features.api.runtime.context import ApiContext

__all__ = (
    "build_rag_document_reservation_purpose",
    "stage_rag_document_upload",
)

LOGGER_NAME = "SoAI.features.api.staging"


async def stage_rag_document_upload(
    request: Request,
    *,
    api_context: ApiContext,
    temp_dir: str,
    max_upload_bytes: int,
    token: CancellationTokenProtocol,
    bridge: StreamingProgressBridge,
    reservation_tracker: StreamingUploadReservationTracker,
) -> tuple[str, int]:
    def on_declared_size(normalized_size: int) -> None:
        reservation_tracker.reserve_declared_remainder(declared_size=normalized_size)

    def report_file_bytes(bytes_done: int) -> None:
        bridge.report(bytes_done)

    try:
        staged = await stage_single_size_declared_upload(
            request,
            parser_semaphore=api_context.dependencies.multipart_parser_semaphore,
            temp_dir=temp_dir,
            max_upload_bytes=max_upload_bytes,
            token=token,
            report_bytes=report_file_bytes,
            report_stream_bytes=bridge.report,
            on_declared_size=on_declared_size,
            write_controller=reservation_tracker,
            logger=get_logger(LOGGER_NAME),
        )
        return staged.part.temp_path, staged.part.size_bytes
    finally:
        reservation_tracker.release_active_reservation()


def build_rag_document_reservation_purpose(
    filename: str,
    resolved_id: str,
) -> StreamingUploadReservationPurpose:
    return StreamingUploadReservationPurpose(
        declared_operation="webui.conversation_rag.upload_document.stage",
        chunk_operation="webui.conversation_rag.upload_document.stage_chunk",
        declared_details={
            "purpose": "rag_document_upload_temp",
            "filename": filename,
            "conv_id": resolved_id,
        },
        chunk_details={
            "purpose": "rag_document_upload_temp",
            "filename": filename,
            "conv_id": resolved_id,
        },
    )
