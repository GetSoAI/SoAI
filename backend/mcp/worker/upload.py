"""SoAI - RAG document upload processing for MCP workers [backend/mcp/worker/upload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.rag_document_identity import normalize_rag_file_type
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.type_catalog import TASK_TYPE_RAG_DOCUMENT_UPLOAD
from mcp.progress_reporting import (
    cleanup_rag_document_entry,
    cleanup_task_registry_entry,
    create_rag_task,
)
from mcp.worker.base64_decode import decode_base64_to_file
from mcp.worker.queue_upload import create_db_entry_and_queue_upload

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "prepare_document_upload",
    "queue_document_upload_response",
    "upload_document_from_base64",
)

LOGGER_NAME = "SoAI.mcp.worker.upload"


async def prepare_document_upload(
    self: MCPWorkerProtocol,
    *,
    conv_id: str,
    user_id: int,
    filename: str,
    file_type: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
    chunking_strategy: str,
    file_size_handler: Callable[[str, str], Awaitable[int]],
    existing_task_id: str | None = None,
    knowledge_attachment_id: str | None = None,
    knowledge_item_index: int | None = None,
    knowledge_source_type: str | None = None,
    knowledge_operation_type: str | None = None,
    client_batch_id: str | None = None,
) -> tuple[str, str]:
    logger = get_logger(LOGGER_NAME)
    doc_id = str(uuid.uuid4())
    temp_dir = self.config.get_str("SYSTEM.PATHS.TEMP")
    if temp_dir is None:
        raise StateError("SYSTEM.PATHS.TEMP is required for MCP upload temp file staging.")
    safe_file_type = normalize_rag_file_type(file_type)
    temp_file = os.path.join(temp_dir, f"{doc_id}.{safe_file_type}")
    db_entry_created = False
    task_id: str | None = None
    try:
        if existing_task_id is None:
            created_task = await create_rag_task(
                self.task_registry,
                task_type=TASK_TYPE_RAG_DOCUMENT_UPLOAD,
                user_id=user_id,
                conv_id=conv_id,
                status=TaskStatus.WORKING,
                progress_total=100,
                metadata={
                    "document_id": doc_id,
                    "filename": filename,
                    "file_type": safe_file_type,
                    "knowledge_attachment_id": knowledge_attachment_id,
                    "knowledge_item_index": knowledge_item_index,
                    "knowledge_source_type": knowledge_source_type,
                    "knowledge_operation_type": knowledge_operation_type,
                    "client_batch_id": client_batch_id,
                },
            )
            task_id = created_task.task_id
        else:
            normalized_task_id = str(existing_task_id or "").strip()
            if not normalized_task_id:
                raise StateError("existing_task_id must be a non-empty string.")
            existing_task = await self.task_registry.get(normalized_task_id)
            if existing_task is None:
                raise StateError(f"Existing upload task not found: {normalized_task_id}")
            if existing_task.status.is_terminal():
                raise StateError(f"Existing upload task is already terminal: {normalized_task_id}")
            task_id = existing_task.task_id
        if not task_id:
            raise StateError("Upload task id missing.")
        file_size = await file_size_handler(task_id, temp_file)
        await create_db_entry_and_queue_upload(
            self,
            doc_id=doc_id,
            conv_id=conv_id,
            user_id=user_id,
            filename=filename,
            file_type=safe_file_type,
            file_size=file_size,
            temp_file=temp_file,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_model=embedding_model,
            chunking_strategy=chunking_strategy,
            task_id=task_id,
            knowledge_attachment_id=knowledge_attachment_id,
            knowledge_item_index=knowledge_item_index,
            knowledge_source_type=knowledge_source_type,
            knowledge_operation_type=knowledge_operation_type,
            client_batch_id=client_batch_id,
        )
        db_entry_created = True
    except RECOVERABLE_EXCEPTIONS as exception:
        try:
            os.unlink(temp_file)
        except FileNotFoundError:
            logger.debug("Temp file already removed during cleanup: %s", temp_file)
        except OSError as error:
            logger.debug("Failed to cleanup temp file %s: %s", temp_file, str(error))
        error_message = str(exception)
        if task_id:

            async def _cleanup_task_registry(
                error_message: str = error_message,
            ) -> None:
                await finalize(
                    self.task_registry,
                    task_id,
                    TaskStatus.FAILED,
                    error_code=500,
                    error_message=error_message,
                )

            await cleanup_task_registry_entry(task_id, _cleanup_task_registry, logger=logger)
        if db_entry_created:
            await cleanup_rag_document_entry(
                doc_id,
                conv_id,
                self.database_files,
                logger=logger,
            )
        raise
    return (doc_id, task_id)


async def queue_document_upload_response(
    self: MCPWorkerProtocol,
    *,
    conv_id: str,
    user_id: int,
    filename: str,
    file_type: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
    chunking_strategy: str,
    file_size_handler: Callable[[str, str], Awaitable[int]],
    existing_task_id: str | None = None,
    knowledge_attachment_id: str | None = None,
    knowledge_item_index: int | None = None,
    knowledge_source_type: str | None = None,
    knowledge_operation_type: str | None = None,
    client_batch_id: str | None = None,
) -> JSONDict:
    doc_id, task_id = await prepare_document_upload(
        self,
        conv_id=conv_id,
        user_id=user_id,
        filename=filename,
        file_type=file_type,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=embedding_model,
        chunking_strategy=chunking_strategy,
        file_size_handler=file_size_handler,
        existing_task_id=existing_task_id,
        knowledge_attachment_id=knowledge_attachment_id,
        knowledge_item_index=knowledge_item_index,
        knowledge_source_type=knowledge_source_type,
        knowledge_operation_type=knowledge_operation_type,
        client_batch_id=client_batch_id,
    )
    return {"document_id": doc_id, "task_id": task_id, "status": "queued"}


async def upload_document_from_base64(
    self: MCPWorkerProtocol,
    *,
    conv_id: str,
    user_id: int,
    filename: str,
    file_type: str,
    content_base64: str,
    max_bytes: int,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    embedding_model: str = "auto",
    chunking_strategy: str = "token_based",
    knowledge_attachment_id: str | None = None,
    knowledge_item_index: int | None = None,
    knowledge_source_type: str | None = None,
    knowledge_operation_type: str | None = None,
    client_batch_id: str | None = None,
) -> JSONDict:
    async def file_size_handler(task_id: str, temp_file: str) -> int:
        return await decode_base64_to_file(
            self,
            task_id,
            content_base64=content_base64,
            destination_path=temp_file,
            label=filename,
            max_bytes=max_bytes,
            progress_start=0,
            progress_end=9,
        )

    return await queue_document_upload_response(
        self,
        embedding_model=embedding_model,
        chunking_strategy=chunking_strategy,
        conv_id=conv_id,
        file_size_handler=file_size_handler,
        file_type=file_type,
        filename=filename,
        chunk_overlap=chunk_overlap,
        chunk_size=chunk_size,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
        knowledge_item_index=knowledge_item_index,
        knowledge_source_type=knowledge_source_type,
        knowledge_operation_type=knowledge_operation_type,
        client_batch_id=client_batch_id,
    )
