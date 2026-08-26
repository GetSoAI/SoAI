"""SoAI - Streaming batch upload exception handling [backend/features/api/routes/file_explorer/upload_transfer/streaming/batch_error_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from core.logging.trace import get_logger
from features.api.routes.file_explorer.upload_transfer.streaming.exception_handling import (
    StreamingUploadErrorPolicy,
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
    moved_paths: list[str],
    created_virtual_paths: list[str],
    file_explorer_core: FileExplorerCoreProtocol,
) -> NoReturn:
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

    async def cleanup_on_task_cancel() -> None:
        await cleanup_cancelled_upload_destinations(
            root_scope=root_scope,
            file_explorer_core=file_explorer_core,
            virtual_paths=created_virtual_paths,
            real_paths=moved_paths,
            logger=get_logger(LOGGER_NAME),
            operation="file_explorer.upload_batch.cancel_cleanup",
        )

    async def cancel_disconnect_action() -> None:
        await cancel_task_after_disconnect_safely(
            registry=registry,
            task_id=task_context.task_id,
            operation="file_explorer.upload.batch.cancel_after_disconnect",
            trace_id=task_context.trace_id,
        )

    await handle_streaming_upload_exception(
        request,
        exception=exception,
        registry=registry,
        task_context=task_context,
        policy=policy,
        operation=OPERATION,
        cleanup_on_task_cancel=cleanup_on_task_cancel,
        cancel_disconnect_action=cancel_disconnect_action,
        recoverable_log_details={"path": path},
        recoverable_disk_space_details={"path": path},
        cancel_cleanup=None,
        cancel_use_uncancel=False,
    )
