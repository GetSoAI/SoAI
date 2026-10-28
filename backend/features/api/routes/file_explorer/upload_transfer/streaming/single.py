"""SoAI - Streaming single file explorer upload handler [backend/features/api/routes/file_explorer/upload_transfer/streaming/single.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.commit_receipt import FileCommitReceipt, FilePublicationUncertainError
from core.files.move_with_cancellation import MoveFileCommittedAfterCancellationError
from core.files.protocols_explorer import (
    FileExplorerCoreProtocol,
    FileSystemRootScopeProtocol,
)
from core.logging.trace import get_logger
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.tasks.enums import TaskStatus
from features.api.routes.file_explorer.upload_transfer.streaming.single_error_handling import (
    StreamingSingleUploadErrorGuard,
)
from features.api.routes.file_explorer.upload_transfer.streaming.single_staging import (
    prepare_single_staged_upload,
)
from features.api.routes.file_explorer.upload_transfer_cleanup import settle_upload_resources
from features.api.routes.file_explorer.upload_transfer_route_setup import (
    build_upload_progress_pump,
    setup_file_explorer_streaming_upload_route,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_server_error
from features.api.runtime.responses import create_json_response_with_task_id
from features.api.runtime.task_execution import finalize_task_safely

__all__ = ("handle_streaming_file_upload",)

LOGGER_NAME = "SoAI.features.api.single"
OPERATION_NOTIFY_UPLOAD_COMPLETE = "file_explorer.upload.single.notify_upload_complete"


async def handle_streaming_file_upload(
    request: Request,
    *,
    file_explorer_core: FileExplorerCoreProtocol,
    root_scope: FileSystemRootScopeProtocol,
    path: str,
    api_context: ApiContext,
) -> JSONResponse:
    setup = await setup_file_explorer_streaming_upload_route(
        request,
        root_scope=root_scope,
        path=path,
        api_context=api_context,
        status_message="Uploading file",
        task_operation="file_explorer_upload",
        file_count=1,
    )
    base_path = setup.base_path
    task_context = setup.task_context
    registry = task_context.registry
    progress = build_upload_progress_pump(
        setup=setup,
        api_context=api_context,
        label="file",
    )
    staged_paths: list[str] = []
    receipt: FileCommitReceipt | None = None
    virtual_destination: str | None = None
    staged_size: int | None = None
    safe_filename: str | None = None
    response: JSONResponse | None = None
    error_guard = StreamingSingleUploadErrorGuard(
        request,
        registry=registry,
        task_context=task_context,
        path=path,
        root_scope=root_scope,
        file_explorer_core=file_explorer_core,
    )

    async with error_guard:
        async with settle_upload_resources(progress, staged_paths):
            progress.start()
            async with cancellation_token_scope(
                api_context.dependencies.token_collection,
                api_context.dependencies.cancellation_history,
                api_context.dependencies.cancellation_event_bus,
                cancellation_id=task_context.cancellation_id,
                owner="file_explorer_upload",
                metadata={"path": path},
            ) as token:
                staged_upload = await prepare_single_staged_upload(
                    request,
                    api_context=api_context,
                    root_scope=root_scope,
                    file_explorer_core=file_explorer_core,
                    base_path=base_path,
                    temp_dir=setup.temp_dir,
                    task_id=task_context.task_id,
                    token=token,
                    progress=progress,
                )
                staged_path = staged_upload.staged_path
                staged_paths.append(staged_path)
                staged_size = staged_upload.staged_size
                safe_filename = staged_upload.safe_filename
                virtual_destination = staged_upload.virtual_destination
                error_guard.set_upload_state(safe_filename=safe_filename)
                error_guard.set_upload_state(
                    virtual_destination=virtual_destination,
                )
                token.raise_if_cancelled()
                try:
                    receipt = await file_explorer_core.move_staged_upload(
                        root_scope=root_scope,
                        temp_path=staged_path,
                        expected_size=staged_size,
                        expected_sha256=staged_upload.content_sha256,
                        file_content_pool=api_context.dependencies.file_content_pool,
                        virtual_destination=virtual_destination,
                        token=token,
                        create_missing_parents=False,
                    )
                except MoveFileCommittedAfterCancellationError as exception:
                    if exception.receipt is None:
                        raise FilePublicationUncertainError(
                            "The upload worker supplied no verified publication receipt."
                        ) from exception
                    receipt = exception.receipt
                    error_guard.set_upload_state(receipt=receipt)
                    raise
                error_guard.set_upload_state(receipt=receipt)
                token.raise_if_cancelled()
                try:
                    await file_explorer_core.notify_upload_complete(
                        root_scope,
                        virtual_destination,
                    )
                except RECOVERABLE_EXCEPTIONS as notify_error:
                    log_handled_exception(
                        get_logger(LOGGER_NAME),
                        notify_error,
                        message="Failed to publish upload completion notification (non-critical).",
                        operation=OPERATION_NOTIFY_UPLOAD_COMPLETE,
                        details={"path": virtual_destination},
                        level="debug",
                    )
                token.raise_if_cancelled()
        await uncancel_then_cleanup(
            finalize_task_safely(
                registry=registry,
                task_id=task_context.task_id,
                status=TaskStatus.COMPLETED,
                trace_id=task_context.trace_id,
                operation="file_explorer.upload.single.finalize_completed",
                result={
                    "path": virtual_destination or base_path,
                    "bytes": staged_size or 0,
                    "count": 1,
                },
                status_message=f"Uploaded {safe_filename}" if safe_filename else "Upload complete",
            )
        )
        response = create_json_response_with_task_id(
            {
                "status": "ok",
                "path": virtual_destination or base_path,
                "size": staged_size or 0,
                "task_id": task_context.task_id,
            },
            task_context.task_id,
            status.HTTP_201_CREATED,
        )
    if response is None:
        raise_server_error(request, "File explorer upload failed to build a response.")
    return response
