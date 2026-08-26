"""SoAI - WebUI RAG batch upload staged file processing [backend/features/api/routes/webui/conversation_rag/documents/batch_upload/processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.webui.conversation_rag.documents.batch_upload.flow import (
    upload_rag_batch_parts,
)
from features.api.routes.webui.conversation_rag.documents.batch_upload.state import (
    RagBatchFailedPart,
    RagBatchKnowledgeState,
    RagBatchUploadMultipartState,
)
from features.api.routes.webui.conversation_rag.knowledge_attachment_failures import (
    record_terminal_knowledge_attachment_item,
)
from features.api.routes.webui.conversation_rag.knowledge_attachment_identity import (
    require_knowledge_attachment_id,
)
from features.api.routes.webui.conversation_rag.knowledge_attachment_lifecycle import (
    ensure_and_publish_knowledge_attachment,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.logging.protocols import StandardLogger
    from core.mcp.protocols_rag import MCPRAGProtocol
    from core.types.json import JSONDict
    from features.api.routes.upload_streaming_multipart_staged_uploads import (
        BatchStagedUpload,
    )
    from features.api.runtime.context import ApiContext

__all__ = ("process_staged_batch_upload",)


async def process_staged_batch_upload(
    *,
    token: CancellationTokenProtocol,
    api_context: ApiContext,
    rag_engine: MCPRAGProtocol,
    resolved_conv_id: str,
    user_id: int,
    staged_upload: BatchStagedUpload,
    include_results: bool,
    results: list[JSONDict],
    logger: StandardLogger,
    batch_state: RagBatchUploadMultipartState,
    knowledge_state: RagBatchKnowledgeState,
    attachment_source: str,
    client_batch_id: str | None,
) -> tuple[int, int, int]:
    knowledge_summary = await ensure_and_publish_knowledge_attachment(
        api_context=api_context,
        conv_id=resolved_conv_id,
        user_id=user_id,
        source_type=attachment_source,
        operation_type="added",
        title=batch_state.last_filename,
        task_id=None,
        client_batch_id=client_batch_id,
    )
    knowledge_attachment_id = require_knowledge_attachment_id(knowledge_summary)
    knowledge_state.knowledge_attachment_id = knowledge_attachment_id
    knowledge_state.latest_summary = knowledge_summary

    async def record_failed_batch_item(failed_part: RagBatchFailedPart) -> None:
        knowledge_state.latest_summary = await record_terminal_knowledge_attachment_item(
            api_context=api_context,
            conv_id=resolved_conv_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_attachment_id,
            item_index=failed_part.item_index,
            filename=failed_part.filename,
            file_type=failed_part.file_type,
            file_size_bytes=failed_part.file_size_bytes,
            rag_status=failed_part.rag_status,
            operation_type="added",
            error_message=failed_part.error_message,
        )

    return await upload_rag_batch_parts(
        token=token,
        rag_engine=rag_engine,
        resolved_conv_id=resolved_conv_id,
        user_id=user_id,
        files=staged_upload.parsed.files,
        relative_paths=staged_upload.relative_paths,
        relative_sizes=staged_upload.relative_sizes,
        include_results=include_results,
        results=results,
        logger=logger,
        knowledge_attachment_id=knowledge_attachment_id,
        knowledge_source_type=attachment_source,
        knowledge_operation_type="added",
        client_batch_id=client_batch_id,
        record_terminal_item=record_failed_batch_item,
        state=batch_state,
    )
