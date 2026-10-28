"""SoAI - Streaming batch file explorer upload handler [backend/features/api/routes/file_explorer/upload_transfer/streaming/batch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Request
from fastapi.responses import JSONResponse

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.commit_receipt import FileCommitReceipt
from core.files.protocols_explorer import (
    FileExplorerCoreProtocol,
    FileSystemRootScopeProtocol,
)
from core.tasks.cancellation_token_scope import cancellation_token_scope
from features.api.routes.file_explorer.upload_transfer.streaming.batch_error_handling import (
    handle_streaming_batch_upload_exception,
)
from features.api.routes.file_explorer.upload_transfer.streaming.batch_processing import (
    StreamingBatchUploadOutcome,
    process_streaming_batch_upload_parts,
)
from features.api.routes.file_explorer.upload_transfer.streaming.batch_result_responses import (
    build_streaming_batch_result_response,
)
from features.api.routes.file_explorer.upload_transfer.streaming.batch_staging import (
    stage_streaming_batch_upload,
)
from features.api.routes.file_explorer.upload_transfer_cleanup import settle_upload_resources
from features.api.routes.file_explorer.upload_transfer_route_setup import (
    build_upload_progress_pump,
    setup_file_explorer_streaming_upload_route,
)
from features.api.runtime.context import ApiContext

__all__ = ("handle_streaming_upload_batch",)

LOGGER_NAME = "SoAI.features.api.batch"
OPERATION = "file_explorer.upload.batch"
_TERMINAL_UPLOAD_EXCEPTIONS: tuple[type[BaseException], ...] = (
    asyncio.CancelledError,
    *HANDLED_RUNTIME_EXCEPTIONS,
)


async def handle_streaming_upload_batch(
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
        status_message="Uploading files",
        task_operation="file_explorer_upload_batch",
        file_count=0,
    )
    base_path = setup.base_path
    task_context = setup.task_context
    registry = task_context.registry
    progress = build_upload_progress_pump(
        setup=setup,
        api_context=api_context,
        label="batch",
    )
    staged_paths: list[str] = []
    receipts: list[FileCommitReceipt] = []
    outcome: StreamingBatchUploadOutcome | None = None

    try:
        async with settle_upload_resources(progress, staged_paths):
            progress.start()
            async with cancellation_token_scope(
                api_context.dependencies.token_collection,
                api_context.dependencies.cancellation_history,
                api_context.dependencies.cancellation_event_bus,
                owner="file_explorer_upload_batch",
                cancellation_id=task_context.cancellation_id,
                metadata={"path": path},
            ) as token:
                parsed_result, parsed_paths, parsed_sizes = await stage_streaming_batch_upload(
                    request,
                    api_context=api_context,
                    temp_dir=setup.temp_dir,
                    token=token,
                    progress=progress,
                    task_id=task_context.task_id,
                )
                staged_paths.extend(part.temp_path for part in parsed_result.files)
                outcome = await process_streaming_batch_upload_parts(
                    staged_parts=parsed_result.files,
                    file_content_pool=api_context.dependencies.file_content_pool,
                    root_scope=root_scope,
                    path=base_path,
                    parsed_paths=parsed_paths,
                    parsed_sizes=parsed_sizes,
                    receipts=receipts,
                    file_explorer_core=file_explorer_core,
                    token=token,
                )
        return await uncancel_then_cleanup(
            build_streaming_batch_result_response(
                registry=registry,
                task_context=task_context,
                path=base_path,
                total_files=len(parsed_result.files),
                outcome=outcome,
            )
        )
    except _TERMINAL_UPLOAD_EXCEPTIONS as exception:
        await uncancel_then_cleanup(
            handle_streaming_batch_upload_exception(
                request,
                exception=exception,
                registry=registry,
                task_context=task_context,
                path=base_path,
                root_scope=root_scope,
                receipts=receipts,
                file_explorer_core=file_explorer_core,
                outcome=outcome,
            )
        )
        raise
