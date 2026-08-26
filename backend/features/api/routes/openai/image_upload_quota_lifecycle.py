"""SoAI - OpenAI image upload quota lifecycle [backend/features/api/routes/openai/image_upload_quota_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import Request

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from features.api.runtime.context import ApiContext, get_request_trace_id
from features.api.runtime.openai_quota_reservations import (
    release_token_quota_reservation_if_present,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

    DispatchErrorHandler = Callable[
        [Request, ApiContext, str | None, dict[str, JSONValue] | None, BaseException],
        Awaitable[None],
    ]

__all__ = (
    "make_upload_dispatch_error_handlers",
    "release_quota_and_log_exception",
)

OPERATION_FEATURES_API_ROUTES_OPENAI_IMAGE_UPLOAD_QUOTA_LIFECYCLE_RELEASE_QUOTA_AND_LOG_EXCEPTION = (
    "features.api.routes.openai.image_upload_quota_lifecycle.release_quota_and_log_exception"
)


LOGGER_NAME = "SoAI.features.api.image_upload_quota_lifecycle"


async def release_quota_and_log_exception(
    request: Request,
    *,
    api_context: ApiContext,
    key_id: str | None,
    reservation: dict[str, JSONValue] | None,
    exception: BaseException,
    operation: str,
    message: str,
    level: str,
    details: dict[str, JSONValue] | None = None,
) -> None:
    trace_id = get_request_trace_id(request)
    await release_token_quota_reservation_if_present(
        api_context,
        key_id,
        reservation,
        trace_id=trace_id,
        operation=f"{operation}.quota_release",
    )
    exception_to_log = exception
    if level == "error":
        exception_to_log = coerce_to_soai_error(exception, operation=operation)
    log_exception(
        get_logger(LOGGER_NAME),
        exception_to_log,
        message=message,
        trace_id=trace_id,
        operation=OPERATION_FEATURES_API_ROUTES_OPENAI_IMAGE_UPLOAD_QUOTA_LIFECYCLE_RELEASE_QUOTA_AND_LOG_EXCEPTION,
        details=details,
        level=level,
    )


def make_upload_dispatch_error_handlers(
    *,
    operation: str,
    recoverable_message: str,
    isolation_message: str,
    coerce_isolation_error: bool = False,
    details: dict[str, JSONValue] | None = None,
) -> tuple[DispatchErrorHandler, DispatchErrorHandler]:
    operation_root = f"api_openai.{operation}"

    async def _on_recoverable_dispatch_error(
        request: Request,
        api_context: ApiContext,
        key_id: str | None,
        reservation: dict[str, JSONValue] | None,
        exception: BaseException,
    ) -> None:
        await release_quota_and_log_exception(
            request,
            api_context=api_context,
            key_id=key_id,
            reservation=reservation,
            exception=exception,
            operation=operation_root,
            message=recoverable_message,
            level="debug",
            details=details,
        )

    async def _on_isolation_dispatch_error(
        request: Request,
        api_context: ApiContext,
        key_id: str | None,
        reservation: dict[str, JSONValue] | None,
        exception: BaseException,
    ) -> None:
        handled_exception = (
            coerce_to_soai_error(exception, operation=operation_root)
            if coerce_isolation_error
            else exception
        )
        await release_quota_and_log_exception(
            request,
            api_context=api_context,
            key_id=key_id,
            reservation=reservation,
            exception=handled_exception,
            operation=operation_root,
            message=isolation_message,
            level="error",
            details=details,
        )

    return _on_recoverable_dispatch_error, _on_isolation_dispatch_error
