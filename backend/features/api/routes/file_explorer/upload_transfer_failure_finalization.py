"""SoAI - File explorer upload failure finalization helpers [backend/features/api/routes/file_explorer/upload_transfer_failure_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from fastapi import Request

from core.errors.exceptions import PayloadTooLargeError, ValidationError
from core.files.upload_size_validation import UPLOAD_MAX_SIZE_EXCEEDED_MESSAGE
from core.tasks.enums import TaskStatus
from features.api.runtime.task_api_errors import finalize_task_and_raise_api_error

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol

__all__ = (
    "finalize_and_raise_payload_too_large",
    "finalize_and_raise_validation_error",
)


async def finalize_and_raise_payload_too_large(
    request: Request,
    *,
    registry: TaskRegistryProtocol,
    task_id: str,
    trace_id: str | None,
    operation: str,
    exception: PayloadTooLargeError,
) -> NoReturn:
    await finalize_task_and_raise_api_error(
        request,
        registry=registry,
        task_id=task_id,
        task_status=TaskStatus.FAILED,
        trace_id=trace_id,
        operation=operation,
        http_status=413,
        error_type="payload_too_large",
        error_message=UPLOAD_MAX_SIZE_EXCEEDED_MESSAGE,
        error_code=413,
        task_error_message=str(exception),
        status_message="Upload too large",
    )


async def finalize_and_raise_validation_error(
    request: Request,
    *,
    registry: TaskRegistryProtocol,
    task_id: str,
    trace_id: str | None,
    operation: str,
    exception: ValidationError,
) -> NoReturn:
    await finalize_task_and_raise_api_error(
        request,
        registry=registry,
        task_id=task_id,
        task_status=TaskStatus.FAILED,
        trace_id=trace_id,
        operation=operation,
        http_status=422,
        error_type="invalid_request_error",
        error_message=str(exception.message),
        error_code=422,
        task_error_message=str(exception),
        status_message="Invalid upload request",
    )
