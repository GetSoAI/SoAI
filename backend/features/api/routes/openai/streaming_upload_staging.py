"""SoAI - OpenAI streaming upload staging with early task creation [backend/features/api/routes/openai/streaming_upload_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

from fastapi import Request, status

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_logging import log_exception
from core.errors.exceptions import InsufficientDiskSpaceError, PayloadTooLargeError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.files.upload_policy import resolve_temp_directory_runtime
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from features.api.routes.openai.streaming_upload_error_handling import (
    finalize_cleanup_and_raise,
    get_content_length_bytes,
)
from features.api.routes.openai.streaming_upload_stage_operations import (
    build_upload_progress_bridge,
    close_bridge_finalize_and_raise,
    create_dispatch_task_for_upload,
    stage_multipart_with_progress,
)
from features.api.routes.upload_streaming_multipart_models import (
    StreamingMultipartResult,
)
from features.api.routes.upload_streaming_multipart_specs import (
    build_streaming_multipart_spec,
)
from features.api.runtime.context import get_request_trace_id

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from features.api.runtime.context import ApiContext

__all__ = ("stage_streaming_openai_multipart_and_create_task",)

LOGGER_NAME_STREAMING_UPLOAD_STAGING = "SoAI.features.api.streaming_upload_staging"
OPERATION_OPENAI_STREAMING_UPLOAD_STAGING_STAGE_MULTIPART_AND_CREATE_TASK = "features.api.routes.openai.streaming_upload_staging.stage_streaming_openai_multipart_and_create_task"


async def stage_streaming_openai_multipart_and_create_task(
    request: Request,
    *,
    api_context: ApiContext,
    command_type: type[Event],
    audit_action: str,
    audit_target: str,
    audit_details: Mapping[str, JSONValue] | None,
    operation: str,
    required_fields: frozenset[str],
    allowed_fields: frozenset[str],
    required_file_fields: frozenset[str],
    allowed_file_fields: frozenset[str],
    allow_multiple_files: bool,
    require_fields_before_files: bool,
    max_file_bytes: int,
    max_total_file_bytes: int | None,
) -> tuple[str, asyncio.Queue[Event], StreamingMultipartResult]:
    temp_dir = resolve_temp_directory_runtime(api_context.dependencies.config)
    fields_required = required_fields
    multipart_spec = build_streaming_multipart_spec(
        required_fields=fields_required,
        allowed_fields=allowed_fields,
        required_file_fields=required_file_fields,
        allowed_file_fields=allowed_file_fields,
        allow_multiple_files=allow_multiple_files,
        require_fields_before_files=require_fields_before_files,
        temp_dir=temp_dir,
        max_file_bytes=max_file_bytes,
        max_total_file_bytes=max_total_file_bytes,
    )
    registry = api_context.dependencies.task_registry

    total_stream_bytes = get_content_length_bytes(request)
    task, reply_queue = await create_dispatch_task_for_upload(
        request,
        registry=registry,
        command_type=command_type,
        audit_action=audit_action,
        audit_target=audit_target,
        audit_details=audit_details,
    )
    bridge = build_upload_progress_bridge(
        registry=registry,
        task_id=task.task_id,
        total_stream_bytes=total_stream_bytes,
        operation=operation,
        cancellation_binder=api_context.dependencies.task_cancellation_binder,
        finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
        cancellation_id=task.cancellation_id,
        owner="openai_upload_progress",
    )
    try:
        parsed, _ = await stage_multipart_with_progress(
            request,
            api_context=api_context,
            bridge=bridge,
            cancellation_id=task.cancellation_id,
            operation=operation,
            spec=multipart_spec,
            total_stream_bytes=total_stream_bytes,
        )
        return (task.task_id, reply_queue, parsed)
    except PayloadTooLargeError as exception:
        await close_bridge_finalize_and_raise(
            request,
            bridge=bridge,
            registry=registry,
            task_id=task.task_id,
            task_status=TaskStatus.FAILED,
            http_status=status.HTTP_413_CONTENT_TOO_LARGE,
            error_type="invalid_request_error",
            error_message=str(exception),
            staged_paths=[],
        )
    except InsufficientDiskSpaceError as exception:
        await close_bridge_finalize_and_raise(
            request,
            bridge=bridge,
            registry=registry,
            task_id=task.task_id,
            task_status=TaskStatus.FAILED,
            http_status=exception.http_status,
            error_type=str(exception.code),
            error_message=str(exception.message),
            staged_paths=[],
        )
    except ValidationError as exception:
        await close_bridge_finalize_and_raise(
            request,
            bridge=bridge,
            registry=registry,
            task_id=task.task_id,
            task_status=TaskStatus.FAILED,
            http_status=status.HTTP_400_BAD_REQUEST,
            error_type="invalid_request_error",
            error_message=str(exception),
            staged_paths=[],
        )
    except TaskCancelledError as exception:
        await close_bridge_finalize_and_raise(
            request,
            bridge=bridge,
            registry=registry,
            task_id=task.task_id,
            task_status=TaskStatus.CANCELLED,
            http_status=499,
            error_type="cancelled",
            error_message=str(exception) or "Request was cancelled.",
            staged_paths=[],
        )
    except asyncio.CancelledError:
        await close_bridge_finalize_and_raise(
            request,
            bridge=bridge,
            registry=registry,
            task_id=task.task_id,
            task_status=TaskStatus.CANCELLED,
            http_status=499,
            error_type="cancelled",
            error_message="Client disconnected.",
            staged_paths=[],
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        await bridge.close()
        log_exception(
            get_logger(LOGGER_NAME_STREAMING_UPLOAD_STAGING),
            exception,
            message="Failed to stage streaming upload",
            operation=OPERATION_OPENAI_STREAMING_UPLOAD_STAGING_STAGE_MULTIPART_AND_CREATE_TASK,
            trace_id=get_request_trace_id(request),
        )
        await finalize_cleanup_and_raise(
            request,
            registry=registry,
            task_id=task.task_id,
            task_status=TaskStatus.FAILED,
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_type="upload_error",
            error_message="Failed to stage upload.",
            staged_paths=[],
        )
