"""SoAI - Streaming batch upload exception handling [backend/features/api/routes/file_explorer/upload_transfer/streaming/batch_error_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, NoReturn

from core.files.commit_receipt import FileCleanupIncompleteError, FileCommitReceipt
from core.logging.trace import get_logger
from features.api.routes.file_explorer.upload_transfer.streaming.exception_handling import (
    StreamingUploadErrorPolicy,
    enrich_upload_publication_error,
    handle_streaming_upload_exception,
)
from features.api.routes.file_explorer.upload_transfer_cleanup import (
    cleanup_cancelled_upload_destinations,
)
from features.api.runtime.task_execution import cancel_task_after_disconnect_safely

if TYPE_CHECKING:
    from fastapi import Request

    from core.files.protocols import FileExplorerCoreProtocol
    from core.files.protocols_explorer import FileSystemRootScopeProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from features.api.routes.file_explorer.upload_transfer.streaming.batch_processing import (
        StreamingBatchUploadOutcome,
    )
    from features.api.routes.file_explorer.upload_transfer_task_context import (
        UploadTaskContext,
    )

__all__ = ("handle_streaming_batch_upload_exception",)

LOGGER_NAME = "SoAI.features.api.batch_error_handling"
OPERATION = "file_explorer.upload.batch"


async def handle_streaming_batch_upload_exception(
    request: Request,
    *,
    exception: BaseException,
    registry: TaskRegistryProtocol,
    task_context: UploadTaskContext,
    path: str,
    root_scope: FileSystemRootScopeProtocol,
    receipts: list[FileCommitReceipt],
    file_explorer_core: FileExplorerCoreProtocol,
    outcome: StreamingBatchUploadOutcome | None = None,
) -> NoReturn:
    completed_result = (
        outcome.to_dict(path=path, total_files=len(outcome.results))
        if outcome is not None
        else None
    )
    if isinstance(exception, FileCleanupIncompleteError):
        exception = enrich_upload_publication_error(
            exception,
            root_scope=root_scope,
            destination=path,
            receipts=receipts,
            details=(
                {
                    **completed_result,
                    "requested_total": completed_result["total"],
                    "unattempted_paths": [],
                }
                if completed_result is not None
                else None
            ),
            append_destination_failure=outcome is None,
        )
    policy = StreamingUploadErrorPolicy(
        logger=get_logger(LOGGER_NAME),
        payload_too_large_finalize_operation="file_explorer.upload.batch.finalize_payload_failed",
        validation_finalize_operation="file_explorer.upload.batch.finalize_invalid",
        cancelled_finalize_operation="file_explorer.upload.batch.finalize_cancelled",
        failed_finalize_operation="file_explorer.upload.batch.finalize_failed",
        disk_space_operation="file_explorer.upload.batch",
        recoverable_log_message="Failed to upload files",
        recoverable_server_error_message="Failed to upload files.",
        cancelled_user_message="File explorer batch upload was cancelled.",
    )

    async def cleanup_on_task_cancel() -> list[str]:
        return await cleanup_cancelled_upload_destinations(
            root_scope=root_scope,
            file_explorer_core=file_explorer_core,
            receipts=receipts,
        )

    await handle_streaming_upload_exception(
        request,
        exception=exception,
        registry=registry,
        task_context=task_context,
        policy=policy,
        operation=OPERATION,
        cleanup_on_task_cancel=cleanup_on_task_cancel,
        cancel_disconnect_action=partial(
            cancel_task_after_disconnect_safely,
            registry=registry,
            task_id=task_context.task_id,
            operation="file_explorer.upload.batch.cancel_after_disconnect",
            trace_id=task_context.trace_id,
        ),
        recoverable_log_details={"path": path},
        recoverable_disk_space_details={"path": path},
        completed_result=completed_result,
    )
