"""SoAI - RAG upload progress bridge and temp file cleanup [backend/features/api/routes/webui/conversation_rag/documents/upload/cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.upload_staging import cleanup_temp_file
from core.logging.protocols import LoggerProtocol
from features.api.routes.upload_streaming_progress import StreamingProgressBridge

__all__ = ("finalize_rag_upload_cleanup",)

OPERATION = "webui.conversation_rag.upload_document.progress_bridge_close"


async def finalize_rag_upload_cleanup(
    logger: LoggerProtocol,
    bridge: StreamingProgressBridge,
    content_size: int | None,
    task_id: str,
    temp_file_path: str | None,
) -> None:
    try:
        await bridge.close(final_bytes_done=content_size)
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_handled_exception(
            logger,
            coerced,
            message="Failed to close RAG upload progress bridge (non-critical).",
            operation=OPERATION,
            details={"task_id": task_id},
            level="debug",
        )
    await cleanup_temp_file(temp_file_path)
