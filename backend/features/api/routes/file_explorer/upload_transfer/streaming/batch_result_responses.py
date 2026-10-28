"""SoAI - Streaming batch upload result responses [backend/features/api/routes/file_explorer/upload_transfer/streaming/batch_result_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import status
from fastapi.responses import JSONResponse

from core.errors.public_projection import build_error_payload
from core.tasks.enums import TaskStatus
from features.api.runtime.responses import create_json_response_with_task_id
from features.api.runtime.task_execution import finalize_task_safely

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from features.api.routes.file_explorer.upload_transfer.streaming.batch_processing import (
        StreamingBatchUploadOutcome,
    )
    from features.api.routes.file_explorer.upload_transfer_task_context import (
        UploadTaskContext,
    )

__all__ = ("build_streaming_batch_result_response",)


async def build_streaming_batch_result_response(
    *,
    registry: TaskRegistryProtocol,
    task_context: UploadTaskContext,
    path: str,
    total_files: int,
    outcome: StreamingBatchUploadOutcome,
) -> JSONResponse:
    if outcome.succeeded <= 0:
        first_failure = next(
            (entry for entry in outcome.results if entry.get("success") is False), None
        )
        failure_code = first_failure.get("code") if first_failure is not None else None
        failure_message = first_failure.get("error") if first_failure is not None else None
        error_payload = build_error_payload(
            failure_message if isinstance(failure_message, str) else "All file uploads failed.",
            code=failure_code if isinstance(failure_code, str) else "file_operation_failed",
            details={"results": outcome.results},
            trace_id=task_context.trace_id,
        )
        await finalize_task_safely(
            registry=registry,
            task_id=task_context.task_id,
            status=TaskStatus.FAILED,
            trace_id=task_context.trace_id,
            operation="file_explorer.upload.batch.finalize_all_failed",
            result={"results": outcome.results, "failed": total_files, "succeeded": 0},
            error_code=400,
            error_message="All file uploads failed",
            status_message="All uploads failed",
        )
        return create_json_response_with_task_id(
            {
                **error_payload,
                "status": "error",
                "message": "All file uploads failed",
                "task_id": task_context.task_id,
                "total": total_files,
                "succeeded": 0,
                "failed": total_files,
                "results": outcome.results,
            },
            task_context.task_id,
            status.HTTP_400_BAD_REQUEST,
        )
    completed_payload = outcome.to_dict(path=path, total_files=total_files)
    batch_status_message = (
        f"Uploaded {total_files} files"
        if outcome.succeeded == total_files
        else f"Uploaded {outcome.succeeded}/{total_files} files"
    )
    await finalize_task_safely(
        registry=registry,
        task_id=task_context.task_id,
        status=TaskStatus.COMPLETED,
        trace_id=task_context.trace_id,
        operation="file_explorer.upload.batch.finalize_completed",
        result=completed_payload,
        status_message=batch_status_message,
    )
    return create_json_response_with_task_id(
        {
            "status": "ok",
            "task_id": task_context.task_id,
            "total": total_files,
            "succeeded": outcome.succeeded,
            "failed": outcome.failed,
            "total_size": outcome.actual_total_size,
            "results": outcome.results,
        },
        task_context.task_id,
        status.HTTP_201_CREATED,
    )
