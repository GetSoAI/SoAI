"""SoAI - Streaming single upload exception handling [backend/features/api/routes/file_explorer/upload_transfer/streaming/single_error_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from types import TracebackType
from typing import TYPE_CHECKING, NoReturn

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.files.commit_receipt import (
    FileCleanupIncompleteError,
    FileCommitReceipt,
    FilePublicationUncertainError,
)
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
    from features.api.routes.file_explorer.upload_transfer_task_context import (
        UploadTaskContext,
    )

__all__ = ("handle_streaming_single_upload_exception",)

LOGGER_NAME = "SoAI.features.api.single_error_handling"
OPERATION_FILE_EXPLORER_UPLOAD = "file_explorer.upload.single"


class StreamingSingleUploadErrorGuard:
    __slots__ = (
        "_file_explorer_core",
        "_receipt",
        "_path",
        "_registry",
        "_request",
        "_root_scope",
        "_safe_filename",
        "_task_context",
        "_virtual_destination",
    )

    def __init__(
        self,
        request: Request,
        *,
        registry: TaskRegistryProtocol,
        task_context: UploadTaskContext,
        path: str,
        root_scope: FileSystemRootScopeProtocol,
        file_explorer_core: FileExplorerCoreProtocol,
    ) -> None:
        self._request = request
        self._registry = registry
        self._task_context = task_context
        self._path = path
        self._root_scope = root_scope
        self._file_explorer_core = file_explorer_core
        self._receipt: FileCommitReceipt | None = None
        self._virtual_destination: str | None = None
        self._safe_filename: str | None = None

    def set_upload_state(
        self,
        *,
        receipt: FileCommitReceipt | None = None,
        virtual_destination: str | None = None,
        safe_filename: str | None = None,
    ) -> None:
        if receipt is not None:
            self._receipt = receipt
        if virtual_destination is not None:
            self._virtual_destination = virtual_destination
        if safe_filename is not None:
            self._safe_filename = safe_filename

    async def __aenter__(self) -> StreamingSingleUploadErrorGuard:
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        del exception_type, traceback
        if exception is None:
            return False
        await uncancel_then_cleanup(
            handle_streaming_single_upload_exception(
                self._request,
                exception=exception,
                registry=self._registry,
                task_context=self._task_context,
                path=self._path,
                root_scope=self._root_scope,
                receipt=self._receipt,
                virtual_destination=self._virtual_destination,
                safe_filename=self._safe_filename,
                file_explorer_core=self._file_explorer_core,
            )
        )


async def handle_streaming_single_upload_exception(
    request: Request,
    *,
    exception: BaseException,
    registry: TaskRegistryProtocol,
    task_context: UploadTaskContext,
    path: str,
    root_scope: FileSystemRootScopeProtocol,
    receipt: FileCommitReceipt | None,
    virtual_destination: str | None,
    safe_filename: str | None,
    file_explorer_core: FileExplorerCoreProtocol,
) -> NoReturn:
    if isinstance(exception, FilePublicationUncertainError | FileCleanupIncompleteError):
        exception = enrich_upload_publication_error(
            exception,
            root_scope=root_scope,
            destination=virtual_destination or path,
            receipts=[receipt] if receipt is not None else [],
        )
    policy = StreamingUploadErrorPolicy(
        logger=get_logger(LOGGER_NAME),
        payload_too_large_finalize_operation="file_explorer.upload.single.finalize_payload_failed",
        validation_finalize_operation="file_explorer.upload.single.finalize_invalid",
        cancelled_finalize_operation="file_explorer.upload.single.finalize_cancelled",
        failed_finalize_operation="file_explorer.upload.single.finalize_failed",
        disk_space_operation="file_explorer.upload.single",
        recoverable_log_message="Failed to upload file",
        recoverable_server_error_message="Failed to upload file.",
        cancelled_user_message="File explorer upload was cancelled.",
    )

    async def cleanup_on_task_cancel() -> list[str]:
        return await cleanup_cancelled_upload_destinations(
            root_scope=root_scope,
            file_explorer_core=file_explorer_core,
            receipts=[receipt] if receipt is not None else [],
        )

    await handle_streaming_upload_exception(
        request,
        exception=exception,
        registry=registry,
        task_context=task_context,
        policy=policy,
        operation=OPERATION_FILE_EXPLORER_UPLOAD,
        cleanup_on_task_cancel=cleanup_on_task_cancel,
        cancel_disconnect_action=partial(
            cancel_task_after_disconnect_safely,
            registry=registry,
            task_id=task_context.task_id,
            operation="file_explorer.upload.single.cancel_after_disconnect",
            trace_id=task_context.trace_id,
        ),
        recoverable_log_details={"path": virtual_destination or path, "filename": safe_filename},
        recoverable_disk_space_details={"path": path},
    )
