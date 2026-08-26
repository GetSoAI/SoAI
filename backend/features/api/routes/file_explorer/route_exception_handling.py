"""SoAI - File explorer route exception handling [backend/features/api/routes/file_explorer/route_exception_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    ConflictError,
    InsufficientDiskSpaceError,
    NotFoundError,
    PayloadTooLargeError,
    SecurityError,
    StateError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from features.api.runtime.context import raise_api_error
from features.api.runtime.errors import (
    raise_conflict,
    raise_invalid_request,
    raise_not_found,
    raise_server_error,
)
from features.api.runtime.task_api_errors import raise_disk_space_api_error

if TYPE_CHECKING:
    from fastapi import Request

    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONValue

__all__ = (
    "FILE_EXPLORER_ROUTE_EXCEPTIONS",
    "handle_file_explorer_route_exception",
)

FILE_EXPLORER_ROUTE_EXCEPTIONS: tuple[type[Exception], ...] = (
    TaskCancelledError,
    SecurityError,
    ValidationError,
    NotFoundError,
    InsufficientDiskSpaceError,
    ConflictError,
    PayloadTooLargeError,
    StateError,
    *RECOVERABLE_EXCEPTIONS,
)


async def handle_file_explorer_route_exception(
    request: Request,
    *,
    exception: BaseException,
    logger: LoggerProtocol,
    coerce_operation: str,
    operation: str,
    log_message: str,
    server_error_message: str,
    log_trace_id: str | None = None,
    log_details: dict[str, JSONValue] | None = None,
    handle_validation_error: bool = True,
    handle_disk_space: bool = False,
    disk_space_operation: str | None = None,
    disk_space_trace_id: str | None = None,
    disk_space_details: dict[str, JSONValue] | None = None,
) -> NoReturn:
    if isinstance(exception, TaskCancelledError):
        raise_api_error(request, 499, "cancelled", "Request cancelled.")
    if isinstance(exception, SecurityError):
        raise_invalid_request(request, exception.message)
    if handle_validation_error and isinstance(exception, ValidationError):
        raise_invalid_request(request, exception.message)
    if isinstance(exception, NotFoundError):
        raise_not_found(request, exception.message)
    if isinstance(exception, ConflictError):
        raise_conflict(request, exception.message)
    if handle_disk_space and isinstance(exception, InsufficientDiskSpaceError):
        await raise_disk_space_api_error(
            request=request,
            exception=exception,
            operation=disk_space_operation or coerce_operation,
            trace_id=disk_space_trace_id,
            details=disk_space_details,
        )
    if isinstance(exception, RECOVERABLE_EXCEPTIONS):
        coerced = coerce_to_soai_error(exception, operation=coerce_operation)
        log_exception(
            logger,
            coerced,
            message=log_message,
            operation=operation,
            trace_id=log_trace_id,
            details=log_details,
        )
        raise_server_error(request, server_error_message)
    raise exception
