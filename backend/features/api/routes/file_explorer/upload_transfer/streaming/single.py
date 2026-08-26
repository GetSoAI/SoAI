"""SoAI - Streaming single file explorer upload handler [backend/features/api/routes/file_explorer/upload_transfer/streaming/single.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_handled_exception
from core.errors.public_projection import build_error_payload
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.move_with_cancellation import MoveFileCommittedAfterCancellationError
from core.files.protocols_explorer import (
    FileExplorerCoreProtocol,
    FileSystemRootScopeProtocol,
)
from core.files.upload_staging import cleanup_temp_file
from core.logging.trace import get_logger
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.tasks.enums import TaskStatus
from features.api.routes.file_explorer.upload_transfer.streaming.single_error_handling import (
    StreamingSingleUploadErrorGuard,
)
from features.api.routes.file_explorer.upload_transfer.streaming.single_staging import (
    prepare_single_staged_upload,
)
from features.api.routes.file_explorer.upload_transfer_cleanup import (
    cleanup_cancelled_upload_destination,
)
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
    staged_path: str | None = None
    moved_destination = False
    real_destination: str | None = None
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

    try:
        async with error_guard:
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
                staged_size = staged_upload.staged_size
                safe_filename = staged_upload.safe_filename
                virtual_destination = staged_upload.virtual_destination
                real_destination = staged_upload.real_destination
                error_guard.set_upload_state(safe_filename=safe_filename)
                error_guard.set_upload_state(
                    virtual_destination=virtual_destination,
                    real_destination=real_destination,
                )
                token.raise_if_cancelled()
                try:
                    real_destination = await file_explorer_core.move_staged_upload(
                        root_scope=root_scope,
                        temp_path=staged_path,
                        expected_size=staged_size,
                        virtual_destination=virtual_destination,
                        token=token,
                        create_missing_parents=False,
                    )
                except MoveFileCommittedAfterCancellationError as exception:
                    real_destination = exception.destination_path
                    moved_destination = True
                    staged_path = None
                    error_guard.set_upload_state(
                        moved_destination=moved_destination,
                        real_destination=real_destination,
                        virtual_destination=virtual_destination,
                    )
                    await cleanup_cancelled_upload_destination(
                        root_scope=root_scope,
                        file_explorer_core=file_explorer_core,
                        virtual_path=virtual_destination,
                        real_path=real_destination,
                        logger=get_logger(LOGGER_NAME),
                        operation="file_explorer.upload.cancel_cleanup_after_commit",
                    )
                    await finalize_task_safely(
                        registry=registry,
                        task_id=task_context.task_id,
                        status=TaskStatus.CANCELLED,
                        trace_id=task_context.trace_id,
                        operation="file_explorer.upload.single.finalize_cancelled_after_commit",
                        error_message=str(exception),
                        status_message=str(exception),
                    )
                    return create_json_response_with_task_id(
                        build_error_payload(
                            "File explorer upload was cancelled.",
                            code="cancelled",
                            details={"task_id": task_context.task_id},
                            trace_id=task_context.trace_id,
                        ),
                        task_context.task_id,
                        499,
                    )
                moved_destination = True
                staged_path = None
                error_guard.set_upload_state(
                    moved_destination=moved_destination,
                    real_destination=real_destination,
                )
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
            await finalize_task_safely(
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
    finally:
        try:
            await uncancel_then_cleanup(progress.close(final_bytes_done=staged_size))
        finally:
            if staged_path:
                await uncancel_then_cleanup(cleanup_temp_file(staged_path))
    if response is None:
        raise_server_error(request, "File explorer upload failed to build a response.")
    return response
