"""SoAI - Streaming single upload exception handling [backend/features/api/routes/file_explorer/upload_transfer/streaming/single_error_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import TYPE_CHECKING, NoReturn

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    ApiError,
    InsufficientDiskSpaceError,
    PayloadTooLargeError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from features.api.routes.file_explorer.upload_transfer.streaming.exception_handling import (
    StreamingUploadErrorPolicy,
    handle_streaming_upload_exception,
)
from features.api.routes.file_explorer.upload_transfer_cleanup import (
    cleanup_cancelled_upload_destination,
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
OPERATION_FILE_EXPLORER_UPLOAD_SINGLE = "file_explorer.upload.single"
OPERATION_FILE_EXPLORER_UPLOAD = "file_explorer.upload.single"


class StreamingSingleUploadErrorGuard:
    __slots__ = (
        "_file_explorer_core",
        "_moved_destination",
        "_path",
        "_real_destination",
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
        self._moved_destination: bool = False
        self._real_destination: str | None = None
        self._virtual_destination: str | None = None
        self._safe_filename: str | None = None

    def set_upload_state(
        self,
        *,
        moved_destination: bool | None = None,
        real_destination: str | None = None,
        virtual_destination: str | None = None,
        safe_filename: str | None = None,
    ) -> None:
        if moved_destination is not None:
            self._moved_destination = bool(moved_destination)
        if real_destination is not None:
            self._real_destination = real_destination
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
        exception_for_handler = self._coerce_upload_exception(exception)
        await handle_streaming_single_upload_exception(
            self._request,
            exception=exception_for_handler,
            registry=self._registry,
            task_context=self._task_context,
            path=self._path,
            root_scope=self._root_scope,
            moved_destination=self._moved_destination,
            real_destination=self._real_destination,
            virtual_destination=self._virtual_destination,
            safe_filename=self._safe_filename,
            file_explorer_core=self._file_explorer_core,
        )

    def _coerce_upload_exception(self, exception: BaseException) -> BaseException:
        if isinstance(
            exception,
            ApiError
            | asyncio.CancelledError
            | TaskCancelledError
            | PayloadTooLargeError
            | ValidationError
            | InsufficientDiskSpaceError,
        ):
            return exception
        if isinstance(exception, RECOVERABLE_EXCEPTIONS):
            return exception
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_FILE_EXPLORER_UPLOAD_SINGLE,
        )
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Streaming single upload failed.",
            operation=OPERATION_FILE_EXPLORER_UPLOAD_SINGLE,
            trace_id=self._task_context.trace_id,
            details={"path": self._path},
            level="warning",
        )
        return coerced


async def handle_streaming_single_upload_exception(
    request: Request,
    *,
    exception: BaseException,
    registry: TaskRegistryProtocol,
    task_context: UploadTaskContext,
    path: str,
    root_scope: FileSystemRootScopeProtocol,
    moved_destination: bool,
    real_destination: str | None,
    virtual_destination: str | None,
    safe_filename: str | None,
    file_explorer_core: FileExplorerCoreProtocol,
) -> NoReturn:
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

    async def cleanup_on_task_cancel() -> None:
        await cleanup_cancelled_upload_destination(
            root_scope=root_scope,
            file_explorer_core=file_explorer_core,
            virtual_path=virtual_destination,
            real_path=real_destination if moved_destination else None,
            logger=get_logger(LOGGER_NAME),
            operation="file_explorer.upload.cancel_cleanup",
        )

    async def cancel_disconnect_action() -> None:
        await cancel_task_after_disconnect_safely(
            registry=registry,
            task_id=task_context.task_id,
            operation="file_explorer.upload.single.cancel_after_disconnect",
            trace_id=task_context.trace_id,
        )

    async def async_cancel_cleanup() -> None:
        await cleanup_cancelled_upload_destination(
            root_scope=root_scope,
            file_explorer_core=file_explorer_core,
            virtual_path=virtual_destination,
            real_path=real_destination if moved_destination else None,
            logger=get_logger(LOGGER_NAME),
            operation="file_explorer.upload.cancel_cleanup",
        )

    await handle_streaming_upload_exception(
        request,
        exception=exception,
        registry=registry,
        task_context=task_context,
        policy=policy,
        operation=OPERATION_FILE_EXPLORER_UPLOAD,
        cleanup_on_task_cancel=cleanup_on_task_cancel,
        cancel_disconnect_action=cancel_disconnect_action,
        recoverable_log_details={"path": virtual_destination or path, "filename": safe_filename},
        recoverable_disk_space_details={"path": path},
        cancel_cleanup=async_cancel_cleanup,
        cancel_use_uncancel=True,
    )
