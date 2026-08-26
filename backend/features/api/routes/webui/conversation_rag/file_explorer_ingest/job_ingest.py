"""SoAI - WebUI File Explorer to RAG ingest queueing [backend/features/api/routes/webui/conversation_rag/file_explorer_ingest/job_ingest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import RateLimitError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.rag_document_identity import normalize_rag_document_identity
from core.tasks.status_transitions import update_progress
from core.timing.retry_backoff import (
    compute_exponential_backoff_seconds,
    parse_retry_after_seconds,
)
from features.api.routes.webui.conversation_rag.file_explorer_ingest.job_steps import (
    iter_file_entries_under_path,
)
from features.api.routes.webui.conversation_rag.file_explorer_ingest.path_formatting import (
    normalize_relative_filename,
)
from features.api.routes.webui.conversation_rag.knowledge_attachment_failures import (
    record_terminal_knowledge_attachment_item,
)

if TYPE_CHECKING:
    from core.files.protocols_explorer import (
        FileExplorerCoreProtocol,
        FileSystemRootScopeProtocol,
    )
    from core.logging.protocols import TraceLogger
    from core.mcp.protocols_rag import MCPRAGProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("ingest_files_under_path",)

OPERATION_LIST_DIRECTORY_INGEST = (
    "webui.conversation_rag.file_explorer_ingest.list_directory.ingest"
)
OPERATION_RESOLVE_REAL_PATH = "webui.conversation_rag.file_explorer_ingest.resolve_real_path"
OPERATION_UPLOAD_DOCUMENT_FROM_PATH = (
    "webui.conversation_rag.file_explorer_ingest.upload_document_from_path"
)

_RATE_LIMIT_BACKOFF_SLEEP_SEC: float = 0.25
_RATE_LIMIT_SLEEP_SEC_MIN: float = 0.25
_RATE_LIMIT_SLEEP_SEC_MAX: float = 30.0
_RATE_LIMIT_MAX_ATTEMPTS: int = 8


def _resolve_rate_limit_sleep_seconds(exception: RateLimitError, attempt: int) -> float:
    retry_after_raw = None
    if exception.headers is not None:
        retry_after_raw = exception.headers.get("Retry-After")
    if retry_after_raw is not None:
        parsed = float(parse_retry_after_seconds(retry_after_raw, default_seconds=0))
        if parsed > 0:
            return max(_RATE_LIMIT_SLEEP_SEC_MIN, min(_RATE_LIMIT_SLEEP_SEC_MAX, parsed))
    return max(
        _RATE_LIMIT_SLEEP_SEC_MIN,
        compute_exponential_backoff_seconds(
            attempt,
            base_seconds=_RATE_LIMIT_BACKOFF_SLEEP_SEC,
            maximum_seconds=_RATE_LIMIT_SLEEP_SEC_MAX,
        ),
    )


async def _record_ingest_terminal_item(
    *,
    api_context: ApiContext,
    resolved_conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    item_index: int,
    relative_filename: str,
    file_type: str,
    file_size_bytes: int | None,
    rag_status: str,
    error_message: str,
) -> None:
    await record_terminal_knowledge_attachment_item(
        api_context=api_context,
        conv_id=resolved_conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
        item_index=item_index,
        filename=relative_filename,
        file_type=file_type,
        file_size_bytes=file_size_bytes,
        rag_status=rag_status,
        operation_type="added",
        error_message=error_message,
    )


async def ingest_files_under_path(
    *,
    api_context: ApiContext,
    rag_engine: MCPRAGProtocol,
    file_explorer_core: FileExplorerCoreProtocol,
    root_scope: FileSystemRootScopeProtocol,
    resolved_conv_id: str,
    user_id: int,
    root_virtual_path: str,
    recursive: bool,
    max_file_bytes: int,
    task_registry: TaskRegistryProtocol,
    task_id: str,
    logger: TraceLogger,
    total_files: int,
    knowledge_attachment_id: str,
    client_batch_id: str | None,
) -> JSONDict:
    queued = 0
    failed = 0
    skipped_oversize = 0
    scanned = 0
    async for virtual_file_path, entry in iter_file_entries_under_path(
        file_explorer_core=file_explorer_core,
        root_scope=root_scope,
        root_virtual_path=root_virtual_path,
        recursive=recursive,
        logger=logger,
        task_id=task_id,
        operation=OPERATION_LIST_DIRECTORY_INGEST,
    ):
        scanned += 1
        relative_filename = normalize_relative_filename(root_virtual_path, virtual_file_path)
        document_identity = normalize_rag_document_identity(
            relative_filename,
            preserve_display_path=True,
        )
        if int(entry.size) > max_file_bytes:
            skipped_oversize += 1
            await _record_ingest_terminal_item(
                api_context=api_context,
                resolved_conv_id=resolved_conv_id,
                user_id=user_id,
                knowledge_attachment_id=knowledge_attachment_id,
                item_index=scanned - 1,
                relative_filename=document_identity.filename,
                file_type=document_identity.file_type,
                file_size_bytes=int(entry.size),
                rag_status="skipped",
                error_message="File exceeds the configured upload limit.",
            )
            continue
        try:
            real_path = file_explorer_core.resolve_real_path(
                root_scope,
                virtual_file_path,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            failed += 1
            await _record_ingest_terminal_item(
                api_context=api_context,
                resolved_conv_id=resolved_conv_id,
                user_id=user_id,
                knowledge_attachment_id=knowledge_attachment_id,
                item_index=scanned - 1,
                relative_filename=document_identity.filename,
                file_type=document_identity.file_type,
                file_size_bytes=int(entry.size),
                rag_status="error",
                error_message=str(exception),
            )
            log_exception(
                logger,
                exception,
                message="Failed to resolve real path during RAG File Explorer ingestion.",
                operation=OPERATION_RESOLVE_REAL_PATH,
                details={"path": virtual_file_path, "task_id": task_id},
            )
            continue
        try:
            attempts = 0
            while True:
                try:
                    await rag_engine.upload_document_from_path(
                        conv_id=resolved_conv_id,
                        source_path=real_path,
                        filename=document_identity.filename,
                        file_type=document_identity.file_type,
                        user_id=user_id,
                        knowledge_attachment_id=knowledge_attachment_id,
                        knowledge_item_index=scanned - 1,
                        knowledge_source_type="file_explorer_folder_import",
                        knowledge_operation_type="added",
                        client_batch_id=client_batch_id,
                    )
                    queued += 1
                    break
                except RateLimitError as exception:
                    if attempts >= _RATE_LIMIT_MAX_ATTEMPTS:
                        raise
                    await asyncio.sleep(_resolve_rate_limit_sleep_seconds(exception, attempts))
                    attempts += 1
        except RECOVERABLE_EXCEPTIONS as exception:
            failed += 1
            await _record_ingest_terminal_item(
                api_context=api_context,
                resolved_conv_id=resolved_conv_id,
                user_id=user_id,
                knowledge_attachment_id=knowledge_attachment_id,
                item_index=scanned - 1,
                relative_filename=document_identity.filename,
                file_type=document_identity.file_type,
                file_size_bytes=int(entry.size),
                rag_status="error",
                error_message=str(exception),
            )
            log_exception(
                logger,
                exception,
                message="Failed to queue file for RAG ingestion.",
                operation=OPERATION_UPLOAD_DOCUMENT_FROM_PATH,
                details={"path": virtual_file_path, "task_id": task_id},
            )
            continue
        if scanned <= 10 or scanned % 10 == 0 or scanned == total_files:
            denominator = max(1, int(total_files))
            processed = queued + failed + skipped_oversize
            percent = min(99, 10 + int((processed / denominator) * 89))
            await update_progress(
                task_registry,
                task_id,
                progress_current=percent,
                percent_override=percent,
                status_message="Queuing documents",
                details=f"Queued: {queued} • Scanned: {scanned}/{total_files} • Failed: {failed} • Skipped: {skipped_oversize}",
            )
    await update_progress(
        task_registry,
        task_id,
        progress_current=99,
        percent_override=99,
        status_message="Finalizing",
        details=f"Queued: {queued} • Failed: {failed} • Skipped: {skipped_oversize}",
    )
    return {
        "queued": queued,
        "failed": failed,
        "skipped_oversize": skipped_oversize,
        "total_files": total_files,
    }
