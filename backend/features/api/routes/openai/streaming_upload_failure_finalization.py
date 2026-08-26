"""SoAI - OpenAI streaming upload task failure finalization [backend/features/api/routes/openai/streaming_upload_failure_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from core.errors.exceptions import ApiError, PayloadTooLargeError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.upload_staging import cleanup_temp_file
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from features.api.routes.openai.streaming_upload_error_handling import (
    finalize_cleanup_and_raise,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import Request

    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

    DispatchErrorHandler = Callable[
        [Request, ApiContext, str | None, JSONDict | None, BaseException],
        Awaitable[None],
    ]

__all__ = (
    "finalize_staged_upload",
    "handle_staged_upload_pre_dispatch_exception",
)


async def finalize_staged_upload(
    registry: TaskRegistryLifecycleView,
    *,
    task_id: str,
    staged_paths: list[str],
    task_status: TaskStatus,
    error_code: int,
    error_message: str,
) -> None:
    await finalize(
        registry,
        task_id,
        task_status,
        error_code=error_code,
        error_message=error_message,
    )
    for staged_path in staged_paths:
        await cleanup_temp_file(staged_path)


async def handle_staged_upload_pre_dispatch_exception(
    request: Request,
    *,
    api_context: ApiContext,
    task_id: str,
    staged_paths: list[str],
    exception: BaseException,
    phase_error_message: str,
    http_exception_already_finalized: bool,
    on_recoverable_dispatch_error: DispatchErrorHandler,
    on_isolation_dispatch_error: DispatchErrorHandler,
) -> None:
    if isinstance(exception, ApiError):
        if http_exception_already_finalized:
            return
        await finalize_staged_upload(
            api_context.dependencies.task_registry,
            task_id=task_id,
            staged_paths=staged_paths,
            task_status=TaskStatus.FAILED,
            error_code=int(exception.http_status),
            error_message=exception.message,
        )
        return
    if isinstance(exception, HTTPException):
        if http_exception_already_finalized:
            return
        error_message = (
            exception.detail if isinstance(exception.detail, str) else phase_error_message
        )
        await finalize_staged_upload(
            api_context.dependencies.task_registry,
            task_id=task_id,
            staged_paths=staged_paths,
            task_status=TaskStatus.FAILED,
            error_code=int(exception.status_code),
            error_message=error_message,
        )
        return
    if isinstance(exception, ValidationError):
        await finalize_cleanup_and_raise(
            request,
            registry=api_context.dependencies.task_registry,
            task_id=task_id,
            task_status=TaskStatus.FAILED,
            http_status=status.HTTP_400_BAD_REQUEST,
            error_type="invalid_request_error",
            error_message=str(exception),
            staged_paths=staged_paths,
        )
    if isinstance(exception, PayloadTooLargeError):
        await finalize_cleanup_and_raise(
            request,
            registry=api_context.dependencies.task_registry,
            task_id=task_id,
            task_status=TaskStatus.FAILED,
            http_status=status.HTTP_413_CONTENT_TOO_LARGE,
            error_type="invalid_request_error",
            error_message=str(exception),
            staged_paths=staged_paths,
        )
    if isinstance(exception, asyncio.CancelledError):
        await finalize_staged_upload(
            api_context.dependencies.task_registry,
            task_id=task_id,
            staged_paths=staged_paths,
            task_status=TaskStatus.CANCELLED,
            error_code=499,
            error_message="Client disconnected.",
        )
        await on_isolation_dispatch_error(request, api_context, None, None, exception)
        return
    if isinstance(exception, RECOVERABLE_EXCEPTIONS):
        await finalize_staged_upload(
            api_context.dependencies.task_registry,
            task_id=task_id,
            staged_paths=staged_paths,
            task_status=TaskStatus.FAILED,
            error_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_message=phase_error_message,
        )
        await on_recoverable_dispatch_error(request, api_context, None, None, exception)
        return
    await finalize_staged_upload(
        api_context.dependencies.task_registry,
        task_id=task_id,
        staged_paths=staged_paths,
        task_status=TaskStatus.FAILED,
        error_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_message=phase_error_message,
    )
    await on_isolation_dispatch_error(request, api_context, None, None, exception)
