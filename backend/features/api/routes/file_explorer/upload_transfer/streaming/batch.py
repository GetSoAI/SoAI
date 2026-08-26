"""SoAI - Streaming batch file explorer upload handler [backend/features/api/routes/file_explorer/upload_transfer/streaming/batch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Request
from fastapi.responses import JSONResponse

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ApiError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.protocols_explorer import (
    FileExplorerCoreProtocol,
    FileSystemRootScopeProtocol,
)
from core.files.upload_staging import cleanup_temp_files
from core.logging.trace import get_logger
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
from features.api.routes.file_explorer.upload_transfer_cleanup import (
    cleanup_cancelled_upload_destinations,
)
from features.api.routes.file_explorer.upload_transfer_route_setup import (
    build_upload_progress_pump,
    setup_file_explorer_streaming_upload_route,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.task_execution import cancel_task_after_disconnect_safely

__all__ = ("handle_streaming_upload_batch",)

LOGGER_NAME = "SoAI.features.api.batch"
OPERATION = "file_explorer.upload.batch"


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
    moved_paths: list[str] = []
    created_virtual_paths: list[str] = []
    outcome: StreamingBatchUploadOutcome | None = None

    try:
        progress.start()
        async with cancellation_token_scope(
            api_context.dependencies.token_collection,
            api_context.dependencies.cancellation_history,
            api_context.dependencies.cancellation_event_bus,
            cancellation_id=task_context.cancellation_id,
            owner="file_explorer_upload_batch",
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
                root_scope=root_scope,
                path=base_path,
                parsed_paths=parsed_paths,
                parsed_sizes=parsed_sizes,
                moved_paths=moved_paths,
                created_virtual_paths=created_virtual_paths,
                file_explorer_core=file_explorer_core,
                token=token,
            )
            return await build_streaming_batch_result_response(
                registry=registry,
                task_context=task_context,
                path=base_path,
                total_files=len(parsed_result.files),
                outcome=outcome,
            )
    except asyncio.CancelledError:
        await uncancel_then_cleanup(
            cancel_task_after_disconnect_safely(
                registry=registry,
                task_id=task_context.task_id,
                operation="file_explorer.upload.batch.cancel_after_disconnect",
                trace_id=task_context.trace_id,
            ),
        )
        await uncancel_then_cleanup(
            cleanup_cancelled_upload_destinations(
                root_scope=root_scope,
                file_explorer_core=file_explorer_core,
                virtual_paths=created_virtual_paths,
                real_paths=moved_paths,
                logger=get_logger(LOGGER_NAME),
                operation="file_explorer.upload_batch.cancel_cleanup",
            ),
        )
        raise
    except ApiError as exception:
        await handle_streaming_batch_upload_exception(
            request,
            exception=exception,
            registry=registry,
            task_context=task_context,
            path=base_path,
            root_scope=root_scope,
            moved_paths=moved_paths,
            created_virtual_paths=created_virtual_paths,
            file_explorer_core=file_explorer_core,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Streaming batch upload failed.",
            operation=OPERATION,
            trace_id=task_context.trace_id,
            details={"path": path},
            level="warning",
        )
        await handle_streaming_batch_upload_exception(
            request,
            exception=exception,
            registry=registry,
            task_context=task_context,
            path=base_path,
            root_scope=root_scope,
            moved_paths=moved_paths,
            created_virtual_paths=created_virtual_paths,
            file_explorer_core=file_explorer_core,
        )
    finally:
        try:
            await uncancel_then_cleanup(
                progress.close(
                    final_bytes_done=(
                        progress.latest_bytes_done if progress.latest_bytes_done > 0 else None
                    ),
                ),
            )
        finally:
            await uncancel_then_cleanup(cleanup_temp_files(staged_paths))
