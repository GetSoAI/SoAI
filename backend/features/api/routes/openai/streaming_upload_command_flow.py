"""SoAI - Shared helper for OpenAI multipart upload command flows [backend/features/api/routes/openai/streaming_upload_command_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request
from starlette.responses import Response

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ApiError, PayloadTooLargeError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from features.api.routes.openai.streaming_upload_dispatch import (
    dispatch_openai_command_with_precreated_task,
)
from features.api.routes.openai.streaming_upload_failure_finalization import (
    finalize_staged_upload,
    handle_staged_upload_pre_dispatch_exception,
)
from features.api.routes.openai.streaming_upload_staging import (
    stage_streaming_openai_multipart_and_create_task,
)
from features.api.runtime.chat_execution.quota_application import (
    apply_token_quota_reservation_to_request,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.responses import apply_task_id_header

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.routes.upload_streaming_multipart_models import (
        StreamingMultipartResult,
    )

    BuildPayload = Callable[
        [str, StreamingMultipartResult, list[str]],
        tuple[dict[str, JSONValue], dict[str, JSONValue]]
        | Awaitable[tuple[dict[str, JSONValue], dict[str, JSONValue]]],
    ]
    DispatchErrorHandler = Callable[
        [Request, ApiContext, str | None, JSONDict | None, BaseException],
        Awaitable[None],
    ]

__all__ = ("execute_openai_multipart_upload_flow",)

LOGGER_NAME = "SoAI.features.api.streaming_upload_command_flow"


async def execute_openai_multipart_upload_flow(
    request: Request,
    *,
    api_context: ApiContext,
    command_type: type[Event],
    audit_action: str,
    audit_target: str,
    operation: str,
    required_fields: frozenset[str],
    allowed_fields: frozenset[str],
    required_file_fields: frozenset[str],
    allowed_file_fields: frozenset[str],
    allow_multiple_files: bool = False,
    require_fields_before_files: bool = False,
    max_file_bytes: int,
    max_total_file_bytes: int | None,
    build_payload: BuildPayload,
    on_recoverable_dispatch_error: DispatchErrorHandler,
    on_isolation_dispatch_error: DispatchErrorHandler,
    response_timeout: float | None = None,
) -> Response:
    task_id, reply_queue, parsed = await stage_streaming_openai_multipart_and_create_task(
        request,
        api_context=api_context,
        command_type=command_type,
        audit_action=audit_action,
        audit_target=audit_target,
        audit_details=None,
        operation=operation,
        required_fields=required_fields,
        allowed_fields=allowed_fields,
        required_file_fields=required_file_fields,
        allowed_file_fields=allowed_file_fields,
        allow_multiple_files=allow_multiple_files,
        require_fields_before_files=require_fields_before_files,
        max_file_bytes=max_file_bytes,
        max_total_file_bytes=max_total_file_bytes,
    )
    staged_paths = [part.temp_path for part in parsed.files]
    try:
        payload_result = build_payload(task_id, parsed, staged_paths)
        command_fields, quota_request_payload = (
            await payload_result if isinstance(payload_result, Awaitable) else payload_result
        )
    except asyncio.CancelledError as exception:
        await handle_staged_upload_pre_dispatch_exception(
            request,
            api_context=api_context,
            task_id=task_id,
            staged_paths=staged_paths,
            exception=exception,
            phase_error_message="Failed to prepare upload payload.",
            http_exception_already_finalized=True,
            on_recoverable_dispatch_error=on_recoverable_dispatch_error,
            on_isolation_dispatch_error=on_isolation_dispatch_error,
        )
        raise
    except (ApiError, HTTPException, PayloadTooLargeError, ValidationError) as exception:
        await handle_staged_upload_pre_dispatch_exception(
            request,
            api_context=api_context,
            task_id=task_id,
            staged_paths=staged_paths,
            exception=exception,
            phase_error_message="Failed to prepare upload payload.",
            http_exception_already_finalized=False,
            on_recoverable_dispatch_error=on_recoverable_dispatch_error,
            on_isolation_dispatch_error=on_isolation_dispatch_error,
        )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced_exception = coerce_to_soai_error(exception, operation=operation)
        log_exception(
            get_logger(LOGGER_NAME),
            coerced_exception,
            message="Unhandled unexpected error while preparing OpenAI multipart upload payload.",
            operation=operation,
        )
        await handle_staged_upload_pre_dispatch_exception(
            request,
            api_context=api_context,
            task_id=task_id,
            staged_paths=staged_paths,
            exception=coerced_exception,
            phase_error_message="Failed to prepare upload payload.",
            http_exception_already_finalized=True,
            on_recoverable_dispatch_error=on_recoverable_dispatch_error,
            on_isolation_dispatch_error=on_isolation_dispatch_error,
        )
        if coerced_exception is exception:
            raise
        raise coerced_exception from exception

    try:
        key_id, reservation, quota_error_response, _prompt_tokens = (
            await apply_token_quota_reservation_to_request(
                request,
                api_context,
                quota_request_payload,
            )
        )
    except asyncio.CancelledError as exception:
        await handle_staged_upload_pre_dispatch_exception(
            request,
            api_context=api_context,
            task_id=task_id,
            staged_paths=staged_paths,
            exception=exception,
            phase_error_message="Failed to process upload quota reservation.",
            http_exception_already_finalized=False,
            on_recoverable_dispatch_error=on_recoverable_dispatch_error,
            on_isolation_dispatch_error=on_isolation_dispatch_error,
        )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced_exception = coerce_to_soai_error(exception, operation=operation)
        log_exception(
            get_logger(LOGGER_NAME),
            coerced_exception,
            message="Unhandled unexpected error while reserving OpenAI multipart upload quota.",
            operation=operation,
        )
        await handle_staged_upload_pre_dispatch_exception(
            request,
            api_context=api_context,
            task_id=task_id,
            staged_paths=staged_paths,
            exception=coerced_exception,
            phase_error_message="Failed to process upload quota reservation.",
            http_exception_already_finalized=False,
            on_recoverable_dispatch_error=on_recoverable_dispatch_error,
            on_isolation_dispatch_error=on_isolation_dispatch_error,
        )
        if coerced_exception is exception:
            raise
        raise coerced_exception from exception

    if quota_error_response is not None:
        await finalize_staged_upload(
            api_context.dependencies.task_registry,
            task_id=task_id,
            staged_paths=staged_paths,
            task_status=TaskStatus.FAILED,
            error_code=quota_error_response.status_code,
            error_message="Quota exceeded.",
        )
        apply_task_id_header(quota_error_response, task_id)
        return quota_error_response

    try:
        return await dispatch_openai_command_with_precreated_task(
            request,
            api_context=api_context,
            task_id=task_id,
            reply_queue=reply_queue,
            command_type=command_type,
            command_fields=command_fields,
            response_timeout=response_timeout,
            staged_paths=staged_paths,
        )
    except asyncio.CancelledError as exception:
        await on_isolation_dispatch_error(
            request,
            api_context,
            key_id,
            reservation,
            exception,
        )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        await on_recoverable_dispatch_error(
            request,
            api_context,
            key_id,
            reservation,
            exception,
        )
        raise
