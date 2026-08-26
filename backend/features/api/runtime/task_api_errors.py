"""SoAI - Task-scoped API error helpers for backend routes [backend/features/api/runtime/task_api_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, NoReturn

from fastapi import Request

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import InsufficientDiskSpaceError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.notifications.system_admin_alerts import create_low_disk_space_admin_alert
from core.tasks.enums import TaskStatus
from features.api.runtime.context import raise_api_error, resolve_api_context
from features.api.runtime.responses import build_task_operation_headers
from features.api.runtime.task_execution import finalize_task_safely

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "finalize_task_and_raise_api_error",
    "log_handled_disk_space_error",
    "raise_api_error_with_optional_task",
    "raise_api_error_with_task",
    "raise_disk_space_api_error",
    "raise_invalid_request_error_with_task",
)

OPERATION_FEATURES_API_RUNTIME_TASK_EXECUTION_LOG_HANDLED_DISK_SPACE_ERROR = (
    "features.api.runtime.task_api_errors.log_handled_disk_space_error"
)
OPERATION_FEATURES_API_RUNTIME_TASK_API_ERRORS_LOW_DISK_NOTIFICATION = (
    "features.api.runtime.task_api_errors.low_disk_notification"
)
LOGGER_NAME = "SoAI.features.api.task_api_errors"


def raise_api_error_with_task(
    request: Request,
    status_code: int,
    error_type: str,
    message: str,
    *,
    task_id: str,
    extra: JSONDict | None = None,
    headers: Mapping[str, str] | None = None,
) -> NoReturn:
    resolved_extra: JSONDict = dict(extra or {})
    resolved_extra["task_id"] = task_id
    resolved_headers = _build_task_error_headers(task_id=task_id, headers=headers)
    raise_api_error(
        request,
        status_code,
        error_type,
        message,
        extra=resolved_extra,
        headers=resolved_headers,
    )


def raise_api_error_with_optional_task(
    request: Request,
    status_code: int,
    error_type: str,
    message: str,
    *,
    task_id: str | None,
    extra: JSONDict | None = None,
    headers: Mapping[str, str] | None = None,
) -> NoReturn:
    if task_id is not None:
        raise_api_error_with_task(
            request,
            status_code,
            error_type,
            message,
            task_id=task_id,
            extra=extra,
            headers=headers,
        )
    resolved_headers = dict(headers) if headers else None
    raise_api_error(
        request,
        status_code,
        error_type,
        message,
        extra=extra,
        headers=resolved_headers,
    )


def raise_invalid_request_error_with_task(
    request: Request,
    *,
    message: str,
    task_id: str,
) -> NoReturn:
    raise_api_error_with_task(
        request,
        422,
        ErrorType.INVALID_REQUEST.value,
        message,
        task_id=task_id,
    )


async def finalize_task_and_raise_api_error(
    request: Request,
    *,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    task_status: TaskStatus,
    operation: str,
    trace_id: str | None,
    http_status: int,
    error_type: str,
    error_message: str,
    result: dict[str, JSONValue] | None = None,
    error_code: int | None = None,
    task_error_message: str | None = None,
    status_message: str | None = None,
    details: dict[str, JSONValue] | None = None,
    extra: JSONDict | None = None,
    headers: Mapping[str, str] | None = None,
) -> NoReturn:
    await finalize_task_safely(
        registry=registry,
        task_id=task_id,
        status=task_status,
        operation=operation,
        trace_id=trace_id,
        result=result,
        error_code=error_code,
        error_message=task_error_message if task_error_message is not None else error_message,
        status_message=status_message,
        details=details,
    )
    raise_api_error_with_task(
        request,
        http_status,
        error_type,
        error_message,
        task_id=task_id,
        extra=extra,
        headers=headers,
    )


def log_handled_disk_space_error(
    *,
    operation: str,
    exception: InsufficientDiskSpaceError,
    trace_id: str | None,
    details: Mapping[str, JSONValue] | None = None,
    message: str | None = None,
) -> None:
    resolved_details: JSONDict = {}
    if exception.details:
        resolved_details.update(dict(exception.details))
    if details:
        resolved_details.update(dict(details))
    resolved_details["operation"] = operation
    log_handled_exception(
        get_logger(LOGGER_NAME),
        exception,
        message=message or str(exception.message),
        operation=OPERATION_FEATURES_API_RUNTIME_TASK_EXECUTION_LOG_HANDLED_DISK_SPACE_ERROR,
        trace_id=trace_id,
        details=resolved_details or None,
        level="warning",
    )


async def raise_disk_space_api_error(
    *,
    request: Request,
    exception: InsufficientDiskSpaceError,
    operation: str,
    trace_id: str | None,
    registry: TaskRegistryLifecycleView | None = None,
    task_id: str | None = None,
    details: Mapping[str, JSONValue] | None = None,
) -> NoReturn:
    resolved_details: JSONDict = {}
    if exception.details:
        resolved_details.update(dict(exception.details))
    if details:
        resolved_details.update(dict(details))
    if task_id:
        resolved_details["task_id"] = task_id
    log_handled_disk_space_error(
        operation=operation,
        exception=exception,
        trace_id=trace_id,
        details=resolved_details,
    )
    await _notify_low_disk_space_noncritical(
        request=request,
        exception=exception,
        fallback_operation_label=operation,
        trace_id=trace_id,
    )
    if registry is not None and task_id:
        await finalize_task_safely(
            registry=registry,
            task_id=task_id,
            status=TaskStatus.FAILED,
            operation=f"{operation}.finalize_failed",
            trace_id=trace_id,
            error_code=exception.http_status,
            error_message="Insufficient disk space.",
            status_message="Insufficient disk space.",
            details=resolved_details,
        )
    api_error_details: JSONDict | None = {"task_id": task_id} if task_id else None
    api_error_headers = (
        _build_task_error_headers(task_id=task_id, headers=None) if task_id else None
    )
    raise_api_error(
        request,
        exception.http_status,
        str(exception.code),
        "Insufficient disk space.",
        extra=api_error_details,
        headers=api_error_headers,
    )


async def _notify_low_disk_space_noncritical(
    *,
    request: Request,
    exception: InsufficientDiskSpaceError,
    fallback_operation_label: str,
    trace_id: str | None,
) -> None:
    try:
        api_context = resolve_api_context(request)
        await create_low_disk_space_admin_alert(
            api_context.dependencies.database_notifications,
            exception=exception,
            fallback_operation_label=fallback_operation_label,
        )
    except RECOVERABLE_EXCEPTIONS as notify_exception:
        log_exception(
            get_logger(LOGGER_NAME),
            notify_exception,
            message="Failed to create low disk space notification.",
            operation=OPERATION_FEATURES_API_RUNTIME_TASK_API_ERRORS_LOW_DISK_NOTIFICATION,
            trace_id=trace_id,
            details={"fallback_operation_label": fallback_operation_label},
            level="warning",
        )


def _build_task_error_headers(
    *,
    task_id: str,
    headers: Mapping[str, str] | None,
) -> dict[str, str]:
    resolved_headers = dict(headers) if headers else {}
    resolved_headers.update(build_task_operation_headers(task_id=task_id, operation_id=None))
    return resolved_headers
