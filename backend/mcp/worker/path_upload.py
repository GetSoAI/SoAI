"""SoAI - RAG document path upload staging for MCP workers [backend/mcp/worker/path_upload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import open_binary
from core.hardware.reservation_claims import claim_reserved_write
from core.tasks.cancellation_token_scope import cancellation_token_scope
from mcp.worker.transfer import run_local_transfer_with_progress
from mcp.worker.upload import queue_document_upload_response

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("upload_worker_document_from_path",)


def _normalize_transfer_progress_bounds(progress_start: int, progress_end: int) -> tuple[int, int]:
    if isinstance(progress_start, bool) or isinstance(progress_end, bool):
        raise StateError("Transfer progress bounds must be integers.")
    normalized_start = int(progress_start)
    normalized_end = int(progress_end)
    if normalized_start < 0 or normalized_start > 100:
        raise StateError("transfer_progress_start must be in [0, 100].")
    if normalized_end < 0 or normalized_end > 100:
        raise StateError("transfer_progress_end must be in [0, 100].")
    if normalized_start > normalized_end:
        raise StateError("transfer_progress_start must be <= transfer_progress_end.")
    return (normalized_start, normalized_end)


async def upload_worker_document_from_path(
    self: MCPWorkerProtocol,
    conv_id: str,
    user_id: int,
    source_path: str,
    filename: str,
    file_type: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    embedding_model: str | None = None,
    chunking_strategy: str = "token_based",
    existing_task_id: str | None = None,
    transfer_progress_start: int = 0,
    transfer_progress_end: int = 9,
    knowledge_attachment_id: str | None = None,
    knowledge_item_index: int | None = None,
    knowledge_source_type: str | None = None,
    knowledge_operation_type: str | None = None,
    client_batch_id: str | None = None,
) -> JSONDict:
    normalized_progress_start, normalized_progress_end = _normalize_transfer_progress_bounds(
        transfer_progress_start,
        transfer_progress_end,
    )
    try:
        source_size = int(os.stat(source_path).st_size)
    except OSError as exception:
        raise StateError("Failed to read upload source size.") from exception
    if source_size <= 0:
        raise ValidationError("Uploaded document is empty.")

    async def file_size_handler(task_id: str, temp_file: str) -> int:
        reservation = self.storage_manager.reserve_disk_space(
            path=temp_file,
            required_bytes=source_size,
            operation="mcp.worker.upload_document_from_path.stage_temp",
            details={
                "source_path": source_path,
                "temp_file": temp_file,
                "filename": filename,
                "required_bytes": source_size,
            },
        )

        def blocking_copy_with_progress(
            report_callback: Callable[[int, int | None], None],
            token: CancellationTokenProtocol,
        ) -> int:
            temp_dir = os.path.dirname(temp_file)
            if temp_dir:
                os.makedirs(temp_dir, exist_ok=True)
            bytes_done = 0
            with (
                open_binary(source_path, mode="rb") as src,
                open_binary(temp_file, mode="wb") as dst,
            ):
                while True:
                    token.raise_if_cancelled()
                    chunk = src.read(MIB_BYTES)
                    if not chunk:
                        break
                    next_total = bytes_done + len(chunk)
                    if next_total > source_size:
                        raise ValidationError("Upload source size changed during transfer.")
                    with claim_reserved_write(reservation, size_bytes=len(chunk)):
                        dst.write(chunk)
                    bytes_done = next_total
                    token.raise_if_cancelled()
                    report_callback(bytes_done, source_size)
            if bytes_done != source_size:
                raise ValidationError("Upload source size changed during transfer.")
            return bytes_done

        try:
            task = await self.task_registry.get(task_id)
            if task is None:
                raise StateError(f"Upload task not found during transfer: {task_id}")
            async with cancellation_token_scope(
                self.token_collection,
                self.cancellation_history,
                self.cancellation_event_bus,
                cancellation_id=task.cancellation_id,
                owner="rag_document_upload_transfer",
                metadata={"task_id": task_id, "source_path": source_path},
            ) as token:
                return await run_local_transfer_with_progress(
                    self,
                    task_id,
                    action="Uploading",
                    label=filename,
                    progress_start=normalized_progress_start,
                    progress_end=normalized_progress_end,
                    total_bytes=source_size,
                    transfer_function=lambda callback: blocking_copy_with_progress(callback, token),
                )
        finally:
            reservation.release()

    return await queue_document_upload_response(
        self,
        existing_task_id=existing_task_id,
        file_size_handler=file_size_handler,
        chunking_strategy=chunking_strategy,
        embedding_model=embedding_model or "auto",
        chunk_overlap=chunk_overlap,
        chunk_size=chunk_size,
        file_type=file_type,
        filename=filename,
        user_id=user_id,
        conv_id=conv_id,
        knowledge_attachment_id=knowledge_attachment_id,
        knowledge_item_index=knowledge_item_index,
        knowledge_source_type=knowledge_source_type,
        knowledge_operation_type=knowledge_operation_type,
        client_batch_id=client_batch_id,
    )
