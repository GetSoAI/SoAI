"""SoAI - Wallpaper error handling [backend/features/api/routes/webui/wallpaper_error_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NoReturn

from fastapi import Request, status

from core.errors.exception_logging import log_exception
from core.errors.exceptions import InsufficientDiskSpaceError, NotFoundError, ValidationError
from core.logging.trace import get_logger
from core.tasks.protocols import TaskRegistryLifecycleView
from features.api.runtime.context import require_request_context
from features.api.runtime.task_api_errors import (
    raise_api_error_with_optional_task,
    raise_disk_space_api_error,
)
from features.api.runtime.upload_error_resolution import resolve_upload_api_error

__all__ = (
    "handle_wallpaper_disk_space_error",
    "handle_wallpaper_exception",
)

LOGGER_NAME = "SoAI.features.api.wallpaper_error_handling"
OPERATION = "api_theme.handle_wallpaper_error"


async def handle_wallpaper_disk_space_error(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    request: Request,
    exception: InsufficientDiskSpaceError,
) -> NoReturn:
    context = require_request_context(request)
    trace_id = context.trace_id
    await raise_disk_space_api_error(
        request=request,
        exception=exception,
        operation="api_theme.handle_wallpaper_disk_space_error",
        trace_id=trace_id,
        registry=registry,
        task_id=task_id,
    )


def handle_wallpaper_exception(
    request: Request,
    exception: Exception,
    action_context: str,
    *,
    task_id: str | None = None,
) -> NoReturn:
    if isinstance(exception, ValidationError):
        error_status, error_code, error_message, _, _ = resolve_upload_api_error(
            exception,
            default_server_message="Failed to process wallpaper upload.",
        )
        raise_api_error_with_optional_task(
            request,
            error_status,
            error_code,
            error_message,
            task_id=task_id,
        )
    if isinstance(exception, ValueError):
        raise_api_error_with_optional_task(
            request,
            status.HTTP_400_BAD_REQUEST,
            "invalid_request_error",
            str(exception),
            task_id=task_id,
        )
    if isinstance(exception, NotFoundError):
        raise_api_error_with_optional_task(
            request,
            status.HTTP_404_NOT_FOUND,
            "not_found_error",
            str(exception),
            task_id=task_id,
        )
    if isinstance(exception, IOError):
        _raise_wallpaper_server_error(request, str(exception), task_id=task_id)
    context = require_request_context(request)
    trace_id = context.trace_id
    log_exception(
        get_logger(LOGGER_NAME),
        exception,
        message=f"Unexpected error during {action_context}",
        operation=OPERATION,
        trace_id=trace_id,
    )
    _raise_wallpaper_server_error(
        request,
        "An unexpected error occurred while processing the wallpaper.",
        task_id=task_id,
    )


def _raise_wallpaper_server_error(
    request: Request,
    message: str,
    *,
    task_id: str | None,
) -> NoReturn:
    raise_api_error_with_optional_task(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "server_error",
        message,
        task_id=task_id,
    )
