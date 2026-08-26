"""SoAI - OpenAI SSE error escalation [backend/core/openai/openai_sse_error_escalation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NoReturn

from core.errors.error_types import ErrorType
from core.errors.exceptions import ApiError
from core.openai.context_overflow_validation import extract_context_overflow_validation
from core.openai.request_requirement_failures import (
    build_openai_request_requirement_failure_details,
    build_openai_request_requirement_failure_message,
    classify_openai_request_requirement_mismatch,
)

__all__ = ("raise_openai_streaming_error",)


def _resolve_openai_sse_error_http_status(error_type: str) -> int:
    match error_type:
        case ErrorType.AUTHENTICATION_ERROR.value:
            return 401
        case ErrorType.FORBIDDEN.value:
            return 403
        case ErrorType.NOT_FOUND.value:
            return 404
        case (
            ErrorType.CONFLICT.value | ErrorType.MODEL_STOPPED.value | ErrorType.MODEL_DELETED.value
        ):
            return 409
        case ErrorType.RATE_LIMIT.value:
            return 429
        case ErrorType.INVALID_REQUEST.value:
            return 422
        case ErrorType.TIMEOUT_ERROR.value:
            return 504
        case (
            ErrorType.SERVICE_UNAVAILABLE.value
            | ErrorType.PLUGIN_UNAVAILABLE.value
            | ErrorType.OVERLOADED.value
        ):
            return 503
        case ErrorType.SERVER_ERROR.value:
            return 500
        case _:
            return 500


def raise_openai_streaming_error(
    parsed_error: tuple[str, str | None, str | None, str | None],
    *,
    operation: str,
) -> NoReturn:
    upstream_message, error_type, _upstream_param, upstream_code = parsed_error
    context_overflow = extract_context_overflow_validation(
        upstream_message,
        None,
        code=upstream_code,
    )
    if context_overflow is not None:
        raise ApiError(
            context_overflow.message,
            code=ErrorType.INVALID_REQUEST.value,
            http_status=422,
            details=context_overflow.to_details(),
            operation=operation,
        )
    mismatch = classify_openai_request_requirement_mismatch(message=upstream_message)
    if mismatch is not None:
        raise ApiError(
            build_openai_request_requirement_failure_message(mismatch),
            code=ErrorType.INVALID_REQUEST.value,
            http_status=422,
            details=build_openai_request_requirement_failure_details(mismatch),
            operation=operation,
        )
    normalized_error_type = (error_type or ErrorType.SERVER_ERROR.value).strip()
    normalized_error_type = normalized_error_type or ErrorType.SERVER_ERROR.value
    if normalized_error_type == ErrorType.PLUGIN_UNAVAILABLE.value:
        raise ApiError(
            "Plugin backend became unavailable. Retry after recovery completes.",
            code=normalized_error_type,
            http_status=503,
            operation=operation,
        )
    raise ApiError(
        (
            "Upstream provider rejected the request."
            if _resolve_openai_sse_error_http_status(normalized_error_type) < 500
            else "Upstream provider request failed."
        ),
        code=normalized_error_type,
        http_status=_resolve_openai_sse_error_http_status(normalized_error_type),
        operation=operation,
    )
