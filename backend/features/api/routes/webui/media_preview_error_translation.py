"""SoAI - WebUI media preview route error translation [backend/features/api/routes/webui/media_preview_error_translation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

import httpx2
from fastapi import Request, status

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError, ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.runtime.network_policy import OfflineModeError
from features.api.runtime.errors import (
    raise_invalid_request,
    raise_not_found,
    raise_offline_mode,
    raise_server_error,
    raise_service_unavailable,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "MEDIA_PREVIEW_REMOTE_ROUTE_EXCEPTIONS",
    "MEDIA_PREVIEW_SCREENSHOT_ROUTE_EXCEPTIONS",
    "raise_for_media_preview_route_exception",
)

MEDIA_PREVIEW_REMOTE_ROUTE_EXCEPTIONS: tuple[type[Exception], ...] = (
    OfflineModeError,
    NotFoundError,
    ValidationError,
    httpx2.HTTPStatusError,
    *HTTP_RECOVERABLE_EXCEPTIONS,
)
MEDIA_PREVIEW_SCREENSHOT_ROUTE_EXCEPTIONS: tuple[type[Exception], ...] = (
    OfflineModeError,
    ValidationError,
    *HTTP_RECOVERABLE_EXCEPTIONS,
)


def raise_for_media_preview_route_exception(
    *,
    request: Request,
    logger: LoggerProtocol,
    exception: Exception,
    operation: str,
    failure_message: str,
    translate_upstream_request_errors: bool,
) -> NoReturn:
    if isinstance(exception, OfflineModeError):
        raise_offline_mode(request, str(exception))
    if isinstance(exception, NotFoundError):
        raise_not_found(request, str(exception))
    if isinstance(exception, ValidationError):
        raise_invalid_request(request, str(exception))
    if isinstance(exception, httpx2.HTTPStatusError):
        _raise_for_upstream_http_status_error(request, exception)
    if translate_upstream_request_errors and isinstance(exception, httpx2.RequestError):
        raise_service_unavailable(
            request,
            f"Upstream request failed: {exception}",
            error_type="download_failed",
        )
    if isinstance(exception, HTTP_RECOVERABLE_EXCEPTIONS):
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_exception(
            logger,
            coerced,
            message=failure_message,
            operation=operation,
            level="warning",
        )
        raise_server_error(request, f"{failure_message}.")
    raise exception


def _raise_for_upstream_http_status_error(
    request: Request,
    exception: httpx2.HTTPStatusError,
) -> NoReturn:
    status_code = int(exception.response.status_code)
    if status_code == status.HTTP_404_NOT_FOUND:
        raise_not_found(request, "Remote media was not found.")
    if status_code == status.HTTP_410_GONE:
        raise_not_found(request, "Remote media is no longer available.")
    if 400 <= status_code < 500:
        raise_invalid_request(request, f"Remote media request failed with status {status_code}.")
    raise_service_unavailable(
        request,
        f"Upstream request failed with status {status_code}.",
        error_type="download_failed",
    )
