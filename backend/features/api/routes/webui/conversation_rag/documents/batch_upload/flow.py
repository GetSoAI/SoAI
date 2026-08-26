"""SoAI - WebUI conversation RAG batch upload flow helpers [backend/features/api/routes/webui/conversation_rag/documents/batch_upload/flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import RateLimitError, ValidationError
from core.errors.public_projection import project_public_exception
from core.files.rag_document_identity import normalize_rag_document_identity
from core.files.upload_size_validation import ensure_staged_size_matches_declared
from core.timing.retry_backoff import parse_retry_after_seconds
from features.api.routes.webui.conversation_rag.documents.batch_upload.staging import (
    cleanup_batch_upload_staged_part,
)
from features.api.routes.webui.conversation_rag.documents.batch_upload.state import (
    RagBatchFailedPart,
    RagBatchUploadMultipartState,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.logging.protocols import StandardLogger
    from core.mcp.protocols_rag import MCPRAGProtocol
    from core.types.json import JSONDict
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingStagedPart,
    )

__all__ = ("upload_rag_batch_parts",)


async def upload_rag_batch_parts(
    *,
    token: CancellationTokenProtocol,
    rag_engine: MCPRAGProtocol,
    resolved_conv_id: str,
    user_id: int,
    files: list[StreamingStagedPart],
    relative_paths: list[str],
    relative_sizes: list[int | None],
    include_results: bool,
    results: list[JSONDict],
    logger: StandardLogger,
    knowledge_attachment_id: str,
    knowledge_source_type: str,
    knowledge_operation_type: str,
    client_batch_id: str | None,
    record_terminal_item: Callable[[RagBatchFailedPart], Awaitable[None]],
    state: RagBatchUploadMultipartState,
) -> tuple[int, int, int]:
    queued = 0
    rate_limited = 0
    failed = 0
    for index, part in enumerate(files):
        state.processed_file_count = index
        token.raise_if_cancelled()
        relative_path = relative_paths[index]
        declared_size = relative_sizes[index]
        document_identity = normalize_rag_document_identity(
            relative_path,
            preserve_display_path=True,
        )
        size_mismatch_error: ValidationError | None = None
        try:
            ensure_staged_size_matches_declared(
                declared_size=declared_size,
                staged_size=part.size_bytes,
            )
        except ValidationError as exception:
            size_mismatch_error = exception
        if size_mismatch_error is not None:
            failed += 1
            await record_terminal_item(
                RagBatchFailedPart(
                    item_index=index,
                    filename=document_identity.filename,
                    file_type=document_identity.file_type,
                    file_size_bytes=part.size_bytes,
                    rag_status="error",
                    error_message=size_mismatch_error.message,
                ),
            )
            if include_results:
                results.append(
                    {
                        "index": index,
                        "filename": document_identity.filename,
                        "status": "failed",
                        "error": size_mismatch_error.message,
                    },
                )
            continue
        try:
            uploaded = await rag_engine.upload_document_from_path(
                conv_id=resolved_conv_id,
                source_path=part.temp_path,
                filename=document_identity.filename,
                file_type=document_identity.file_type,
                user_id=user_id,
                existing_task_id=None,
                transfer_progress_start=0,
                transfer_progress_end=9,
                knowledge_attachment_id=knowledge_attachment_id,
                knowledge_item_index=index,
                knowledge_source_type=knowledge_source_type,
                knowledge_operation_type=knowledge_operation_type,
                client_batch_id=client_batch_id,
            )
            queued += 1
            state.queued_file_count += 1
            if include_results:
                item = dict(uploaded)
                item["index"] = index
                item["filename"] = document_identity.filename
                results.append(item)
        except RateLimitError as exception:
            rate_limited += 1
            public_error_message = project_public_exception(exception).message
            retry_after_raw = exception.headers.get("Retry-After") if exception.headers else None
            retry_after_seconds = parse_retry_after_seconds(
                retry_after_raw,
                default_seconds=0,
            )
            await record_terminal_item(
                RagBatchFailedPart(
                    item_index=index,
                    filename=document_identity.filename,
                    file_type=document_identity.file_type,
                    file_size_bytes=part.size_bytes,
                    rag_status="error",
                    error_message=public_error_message,
                ),
            )
            if include_results:
                results.append(
                    {
                        "index": index,
                        "filename": document_identity.filename,
                        "status": "rate_limited",
                        "retry_after_seconds": retry_after_seconds,
                        "error": public_error_message,
                    },
                )
        except (ValidationError, RuntimeError, OSError, TypeError, ValueError) as exception:
            failed += 1
            public_error_message = project_public_exception(exception).message
            await record_terminal_item(
                RagBatchFailedPart(
                    item_index=index,
                    filename=document_identity.filename,
                    file_type=document_identity.file_type,
                    file_size_bytes=part.size_bytes,
                    rag_status="error",
                    error_message=public_error_message,
                ),
            )
            if include_results:
                results.append(
                    {
                        "index": index,
                        "filename": document_identity.filename,
                        "status": "failed",
                        "error": public_error_message,
                    },
                )
        finally:
            await uncancel_then_cleanup(
                cleanup_batch_upload_staged_part(
                    temp_path=part.temp_path,
                    logger=logger,
                    resolved_conv_id=resolved_conv_id,
                ),
            )
            state.processed_file_count = index + 1
    return queued, rate_limited, failed
