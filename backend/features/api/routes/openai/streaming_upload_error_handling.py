"""SoAI - OpenAI streaming upload error handling and part extraction [backend/features/api/routes/openai/streaming_upload_error_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from fastapi import Request, status

from core.errors.exceptions import ValidationError
from core.files.upload_staging import cleanup_temp_file
from core.tasks.enums import TaskStatus
from features.api.routes.upload_streaming_multipart_models import StreamingStagedPart
from features.api.runtime.context import get_request_trace_id
from features.api.runtime.task_api_errors import raise_api_error_with_task
from features.api.runtime.task_execution import finalize_task_safely

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryLifecycleView

__all__ = (
    "extract_optional_single_file",
    "extract_single_file",
    "finalize_cleanup_and_raise",
    "finalize_cleanup_and_raise_invalid_request",
    "get_content_length_bytes",
)


def get_content_length_bytes(request: Request) -> int | None:
    raw = request.headers.get("content-length")
    if not raw:
        return None
    try:
        parsed = int(raw)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def extract_single_file(
    staged_files: list[StreamingStagedPart],
    field_name: str,
) -> StreamingStagedPart:
    matches = [part for part in staged_files if part.field_name == field_name]
    if len(matches) != 1:
        raise ValidationError(f"Exactly one '{field_name}' file must be provided.")
    return matches[0]


def extract_optional_single_file(
    staged_files: list[StreamingStagedPart],
    field_name: str,
) -> StreamingStagedPart | None:
    matches = [part for part in staged_files if part.field_name == field_name]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValidationError(f"At most one '{field_name}' file may be provided.")
    return matches[0]


async def finalize_cleanup_and_raise(
    request: Request,
    *,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    task_status: TaskStatus,
    http_status: int,
    error_type: str,
    error_message: str,
    staged_paths: list[str],
) -> NoReturn:
    await finalize_task_safely(
        registry=registry,
        task_id=task_id,
        status=task_status,
        operation="api_openai.streaming_upload.finalize_and_raise",
        trace_id=get_request_trace_id(request),
        error_code=http_status,
        error_message=error_message,
    )
    for staged_path in staged_paths:
        await cleanup_temp_file(staged_path)
    raise_api_error_with_task(
        request,
        http_status,
        error_type,
        error_message,
        task_id=task_id,
    )


async def finalize_cleanup_and_raise_invalid_request(
    request: Request,
    *,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    error_message: str,
    staged_paths: list[str],
) -> NoReturn:
    await finalize_cleanup_and_raise(
        request,
        registry=registry,
        task_id=task_id,
        task_status=TaskStatus.FAILED,
        http_status=status.HTTP_400_BAD_REQUEST,
        error_type="invalid_request_error",
        error_message=error_message,
        staged_paths=staged_paths,
    )
