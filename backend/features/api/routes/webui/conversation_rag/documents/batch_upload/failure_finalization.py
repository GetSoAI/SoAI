"""SoAI - WebUI RAG batch upload knowledge failure finalization [backend/features/api/routes/webui/conversation_rag/documents/batch_upload/failure_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.files.rag_document_identity import normalize_rag_document_identity
from features.api.routes.webui.conversation_rag.documents.batch_upload.state import (
    RagBatchUploadMultipartState,
)
from features.api.routes.webui.conversation_rag.knowledge_attachment_failures import (
    finalize_knowledge_attachment_failure,
    record_terminal_knowledge_attachment_item,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingStagedPart,
    )
    from features.api.runtime.context import ApiContext

__all__ = ("finalize_batch_upload_failure",)


async def _record_unprocessed_items(
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    files: list[StreamingStagedPart],
    relative_paths: list[str],
    start_index: int,
    rag_status: str,
    error_message: str,
) -> JSONDict | None:
    latest_summary: JSONDict | None = None
    for item_index in range(start_index, len(files)):
        part = files[item_index]
        has_relative_path = item_index < len(relative_paths)
        filename = relative_paths[item_index] if has_relative_path else part.original_filename
        document_identity = normalize_rag_document_identity(
            filename,
            preserve_display_path=has_relative_path,
        )
        latest_summary = await record_terminal_knowledge_attachment_item(
            api_context=api_context,
            conv_id=conv_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_attachment_id,
            item_index=item_index,
            filename=document_identity.filename,
            file_type=document_identity.file_type,
            file_size_bytes=part.size_bytes,
            rag_status=rag_status,
            operation_type="added",
            error_message=error_message,
        )
    return latest_summary


async def finalize_batch_upload_failure(
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str | None,
    files: list[StreamingStagedPart],
    relative_paths: list[str],
    state: RagBatchUploadMultipartState,
    processing_state: str,
    terminal_item_status: str,
    error_message: str,
) -> JSONDict | None:
    if knowledge_attachment_id is None:
        return None
    latest_summary = await _record_unprocessed_items(
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
        files=files,
        relative_paths=relative_paths,
        start_index=state.processed_file_count,
        rag_status=terminal_item_status,
        error_message=error_message,
    )
    if state.queued_file_count > 0:
        return latest_summary
    finalized = await finalize_knowledge_attachment_failure(
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
        processing_state=processing_state,
        terminal_item_status=terminal_item_status,
        error_message=error_message,
        state="unused",
    )
    return finalized if finalized is not None else latest_summary
