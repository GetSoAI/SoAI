"""SoAI - API runtime error helpers [backend/features/api/runtime/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from fastapi import status
from fastapi.responses import JSONResponse

from core.errors.error_types import ErrorType
from core.errors.status_mapping import error_type_to_status_code
from core.openai.request_requirement_failures import (
    build_openai_request_requirement_failure_details,
    classify_openai_request_requirement_mismatch,
)
from core.runtime.protocols import ConnectionProtocol
from core.tasks.errors import TaskIDCollisionError
from features.api.runtime.context import raise_api_error
from features.api.runtime.error_response_fields import (
    extract_error_fields_from_response,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "handle_task_id_collision",
    "raise_action_failed",
    "raise_action_not_supported",
    "raise_bad_gateway",
    "raise_bad_request",
    "raise_conflict",
    "raise_error_type",
    "raise_forbidden",
    "raise_from_error_response",
    "raise_gateway_timeout",
    "raise_invalid_request",
    "raise_not_found",
    "raise_offline_mode",
    "raise_payload_too_large",
    "raise_precondition_failed",
    "raise_rate_limit",
    "raise_server_error",
    "raise_service_unavailable",
    "raise_task_registry_unavailable",
    "raise_unauthorized",
)


def raise_not_found(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str = ErrorType.NOT_FOUND.value,
    extra: JSONDict | None = None,
) -> NoReturn:
    raise_api_error(request, status.HTTP_404_NOT_FOUND, error_type, message, extra=extra)


def raise_invalid_request(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str = ErrorType.INVALID_REQUEST.value,
    extra: JSONDict | None = None,
) -> NoReturn:
    details = dict(extra) if isinstance(extra, dict) else None
    if error_type == ErrorType.INVALID_REQUEST.value:
        mismatch = classify_openai_request_requirement_mismatch(message=message, details=details)
        if mismatch is not None:
            mismatch_details = build_openai_request_requirement_failure_details(mismatch)
            details = {**mismatch_details, **(details or {})}
    raise_api_error(
        request,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        error_type,
        message,
        extra=details,
    )


def raise_bad_request(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str = ErrorType.INVALID_REQUEST.value,
    extra: JSONDict | None = None,
) -> NoReturn:
    raise_api_error(request, status.HTTP_400_BAD_REQUEST, error_type, message, extra=extra)


def raise_bad_gateway(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str = ErrorType.SERVER_ERROR.value,
    extra: JSONDict | None = None,
) -> NoReturn:
    del message, extra
    raise_api_error(
        request,
        status.HTTP_502_BAD_GATEWAY,
        error_type,
        "Upstream service request failed.",
    )


def raise_payload_too_large(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str = ErrorType.INVALID_REQUEST.value,
    extra: JSONDict | None = None,
) -> NoReturn:
    raise_api_error(request, status.HTTP_413_CONTENT_TOO_LARGE, error_type, message, extra=extra)


def raise_precondition_failed(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str,
    extra: JSONDict | None = None,
) -> NoReturn:
    raise_api_error(request, status.HTTP_412_PRECONDITION_FAILED, error_type, message, extra=extra)


def raise_rate_limit(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str = ErrorType.RATE_LIMIT.value,
    extra: JSONDict | None = None,
    headers: dict[str, str] | None = None,
) -> NoReturn:
    raise_api_error(
        request,
        status.HTTP_429_TOO_MANY_REQUESTS,
        error_type,
        message,
        extra=extra,
        headers=headers,
    )


def raise_action_failed(request: ConnectionProtocol, message: str) -> NoReturn:
    raise_api_error(request, status.HTTP_400_BAD_REQUEST, "action_failed", message)


def raise_error_type(
    request: ConnectionProtocol,
    error_type: ErrorType,
    message: str,
    *,
    extra: JSONDict | None = None,
) -> NoReturn:
    raise_api_error(
        request,
        error_type_to_status_code(error_type),
        error_type.value,
        message,
        extra=extra,
    )


def raise_service_unavailable(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str = ErrorType.SERVICE_UNAVAILABLE.value,
    extra: JSONDict | None = None,
) -> NoReturn:
    del message, extra
    raise_api_error(
        request,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        error_type,
        "Service temporarily unavailable.",
    )


def raise_conflict(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str = ErrorType.CONFLICT.value,
    extra: JSONDict | None = None,
) -> NoReturn:
    raise_api_error(request, status.HTTP_409_CONFLICT, error_type, message, extra=extra)


def raise_gateway_timeout(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str = ErrorType.TIMEOUT_ERROR.value,
    extra: JSONDict | None = None,
) -> NoReturn:
    del message, extra
    raise_api_error(
        request,
        status.HTTP_504_GATEWAY_TIMEOUT,
        error_type,
        "Upstream service timed out.",
    )


def raise_server_error(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str = ErrorType.SERVER_ERROR.value,
    extra: JSONDict | None = None,
) -> NoReturn:
    del message, extra
    raise_api_error(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type,
        "Internal server error.",
    )


def raise_from_error_response(
    request: ConnectionProtocol,
    response: JSONResponse,
    *,
    fallback_message: str = "Internal server error.",
    fallback_error_type: str = ErrorType.SERVER_ERROR.value,
) -> NoReturn:
    message, error_type = extract_error_fields_from_response(
        response,
        fallback_message=fallback_message,
        fallback_error_type=fallback_error_type,
    )
    if response.status_code >= 500:
        message = fallback_message
        error_type = fallback_error_type
    raise_api_error(request, response.status_code, error_type, message)


def raise_forbidden(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str = ErrorType.FORBIDDEN.value,
    extra: JSONDict | None = None,
) -> NoReturn:
    raise_api_error(request, status.HTTP_403_FORBIDDEN, error_type, message, extra=extra)


def raise_unauthorized(
    request: ConnectionProtocol,
    message: str,
    *,
    error_type: str = ErrorType.AUTHENTICATION_ERROR.value,
    extra: JSONDict | None = None,
) -> NoReturn:
    raise_api_error(request, status.HTTP_401_UNAUTHORIZED, error_type, message, extra=extra)


def raise_offline_mode(request: ConnectionProtocol, message: str) -> NoReturn:
    raise_api_error(request, status.HTTP_423_LOCKED, "offline_mode", message)


def raise_action_not_supported(request: ConnectionProtocol, message: str) -> NoReturn:
    raise_api_error(
        request,
        status.HTTP_400_BAD_REQUEST,
        ErrorType.ACTION_NOT_SUPPORTED.value,
        message,
    )


def raise_task_registry_unavailable(request: ConnectionProtocol) -> NoReturn:
    raise_api_error(
        request,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        ErrorType.SERVICE_UNAVAILABLE.value,
        "Task registry not initialized.",
    )


def handle_task_id_collision(
    request: ConnectionProtocol,
    exception: TaskIDCollisionError,
) -> NoReturn:
    raise_api_error(
        request,
        status.HTTP_409_CONFLICT,
        "task_id_collision",
        f"Task with ID '{exception.task_id}' already exists (status: {exception.existing_status}).",
    )
