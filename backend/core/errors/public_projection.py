"""SoAI - Trusted projection of internal exceptions to public error payloads [backend/core/errors/public_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exceptions import ApiError, SoAIError
from core.errors.memory_exhaustion import resolve_memory_exhaustion_message
from core.errors.payload import ErrorPublicPayload
from core.errors.status_mapping import error_type_to_status_code
from core.openai.context_overflow_validation import extract_context_overflow_validation

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_error_payload",
    "build_error_response_content",
    "project_public_error",
    "project_public_error_code",
    "project_public_exception",
    "project_public_status_error",
)


def build_error_response_content(
    exception: BaseException,
    *,
    trace_id: str | None = None,
) -> JSONDict:
    error = coerce_to_soai_error(exception, trace_id=trace_id)
    return {"error": project_public_error(error, trace_id=trace_id).to_dict()}


def build_error_payload(
    message: str,
    *,
    code: str,
    details: Mapping[str, JSONValue] | None = None,
    trace_id: str | None = None,
) -> JSONDict:
    payload = ErrorPublicPayload(code=code, message=message, details=details, trace_id=trace_id)
    return {"error": payload.to_dict()}


def project_public_error(
    error: SoAIError,
    *,
    trace_id: str | None = None,
) -> ErrorPublicPayload:
    resolved_trace_id = trace_id or error.trace_id
    status_code = int(error.http_status)
    if error.code == "database_timeout":
        return _project_database_timeout(error, trace_id=resolved_trace_id)
    if error.code == ErrorType.PLUGIN_UNAVAILABLE.value:
        return ErrorPublicPayload(
            code=error.code,
            message="Plugin backend became unavailable. Retry after recovery completes.",
            trace_id=resolved_trace_id,
        )
    memory_message = resolve_memory_exhaustion_message(error.code)
    if memory_message is not None:
        return ErrorPublicPayload(
            code=error.code,
            message=memory_message,
            trace_id=resolved_trace_id,
        )
    context_overflow = extract_context_overflow_validation(error.message, error.details)
    if context_overflow is not None:
        return ErrorPublicPayload(
            code=error.code,
            message=context_overflow.message,
            details=context_overflow.to_details(),
            trace_id=resolved_trace_id,
        )
    if status_code >= 500:
        return ErrorPublicPayload(
            code=error.code,
            message="Internal server error.",
            trace_id=resolved_trace_id,
        )
    if isinstance(error, ApiError):
        return ErrorPublicPayload(
            code=error.code,
            message=error.message,
            details=error.details,
            trace_id=resolved_trace_id,
        )
    if status_code == 404:
        message = "Resource not found."
    elif status_code == 403:
        message = "Access denied."
    elif status_code == 409:
        message = "The request conflicts with the current state."
    elif status_code == 429:
        message = "Rate limit exceeded."
    else:
        message = "Request validation failed."
    return ErrorPublicPayload(
        code=error.code,
        message=message,
        trace_id=resolved_trace_id,
    )


def _project_database_timeout(
    error: SoAIError,
    *,
    trace_id: str | None,
) -> ErrorPublicPayload:
    details: dict[str, JSONValue] = {}
    source = error.details or {}
    operation_id = source.get("operation_id")
    status_url = source.get("status_url")
    retry_guidance = source.get("retry_guidance")
    status = source.get("status")
    if isinstance(operation_id, str) and operation_id:
        details["operation_id"] = operation_id
    if isinstance(status_url, str) and status_url:
        details["status_url"] = status_url
    if isinstance(retry_guidance, str) and retry_guidance:
        details["retry_guidance"] = retry_guidance
    if isinstance(status, str) and status:
        details["status"] = status
    return ErrorPublicPayload(
        code="database_timeout",
        message="Database operation timed out. Check its status before retrying.",
        details=details or None,
        trace_id=trace_id,
    )


def project_public_exception(
    exception: BaseException,
    *,
    trace_id: str | None = None,
) -> ErrorPublicPayload:
    if isinstance(exception, SoAIError):
        return project_public_error(exception, trace_id=trace_id)
    return ErrorPublicPayload(
        code="internal_error",
        message="Internal server error.",
        trace_id=trace_id,
    )


def project_public_status_error(
    *,
    status_code: int,
    code: str | int,
    message: str,
    details: Mapping[str, JSONValue] | None = None,
    trace_id: str | None = None,
) -> ErrorPublicPayload:
    return project_public_error(
        ApiError(
            message,
            code=code,
            http_status=status_code,
            details=details,
            trace_id=trace_id,
        ),
        trace_id=trace_id,
    )


def project_public_error_code(
    *,
    code: str,
    message: str,
    details: Mapping[str, JSONValue] | None = None,
    trace_id: str | None = None,
) -> ErrorPublicPayload:
    normalized_code = str(code).strip()
    status_code: int | None = 500 if normalized_code == "internal_error" else None
    if status_code is None:
        try:
            status_code = error_type_to_status_code(ErrorType(normalized_code))
        except ValueError:
            status_code = None
    if status_code is None:
        return ErrorPublicPayload(
            code=normalized_code,
            message=message,
            details=details,
            trace_id=trace_id,
        )
    projected = project_public_status_error(
        status_code=status_code,
        code=normalized_code,
        message=message,
        details=details,
        trace_id=trace_id,
    )
    return ErrorPublicPayload(
        code=normalized_code,
        message=projected.message,
        details=projected.details,
        trace_id=trace_id,
    )
