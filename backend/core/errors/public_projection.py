"""SoAI - Trusted projection of internal exceptions to public error payloads [backend/core/errors/public_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING

from core.errors.classified_failure_projection import project_classified_failure
from core.errors.error_types import ErrorType
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exceptions import ApiError, SoAIError
from core.errors.http_status_classification import resolve_execution_error_type_for_http_status
from core.errors.memory_exhaustion import resolve_memory_exhaustion_message
from core.errors.payload import ErrorPublicPayload
from core.errors.status_mapping import error_type_to_status_code
from core.openai.context_overflow_validation import extract_context_overflow_validation
from core.openai.model_output_contract_errors import (
    INVALID_TOOL_CALL_JSON_FAILURE_TYPE,
    is_invalid_tool_call_json_contract_error,
)
from core.openai.provider_error_explanations import (
    build_upstream_provider_public_error,
    resolve_upstream_failure_type,
)
from core.openai.provider_transport import has_upstream_provider_marker

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "apply_public_error_payload",
    "build_error_payload",
    "build_error_response_content",
    "project_public_error",
    "project_public_error_code",
    "project_public_exception",
    "project_public_status_error",
    "project_specific_public_error",
    "project_specific_public_exception",
)


def apply_public_error_payload(error: SoAIError, payload: ErrorPublicPayload) -> None:
    error.public_message = payload.message
    error.public_param = payload.param
    error.public_details = payload.details
    error.code = payload.code
    if payload.http_status is not None:
        error.http_status = payload.http_status
    if payload.trace_id is not None:
        error.trace_id = payload.trace_id


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
    specific = project_specific_public_error(error, trace_id=trace_id)
    if specific is not None:
        return specific
    resolved_trace_id = trace_id or error.trace_id
    status_code = int(error.http_status)
    if status_code >= 500:
        return ErrorPublicPayload(
            code=error.code,
            message="Internal server error.",
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


def project_specific_public_error(
    error: SoAIError,
    *,
    trace_id: str | None = None,
) -> ErrorPublicPayload | None:
    resolved_trace_id = trace_id or error.trace_id
    status_code = int(error.http_status)
    if isinstance(error.public_message, str) and error.public_message.strip():
        return ErrorPublicPayload(
            code=error.code,
            message=error.public_message,
            param=error.public_param,
            details=error.public_details,
            http_status=status_code,
            trace_id=resolved_trace_id,
        )
    classified_failure = project_classified_failure(error, trace_id=resolved_trace_id)
    if classified_failure is not None:
        return classified_failure
    if error.code == "database_acceptance_unresolved":
        source = error.details or {}
        details = {
            name: source[name]
            for name in ("operation_id", "status_url", "status", "retry_guidance")
            if isinstance(source.get(name), str)
        }
        return ErrorPublicPayload(
            code=error.code,
            message="Upload acceptance could not be confirmed. Check its status before retrying.",
            details=details or None,
            trace_id=resolved_trace_id,
        )
    if error.code == "database_timeout":
        return _project_database_timeout(error, trace_id=resolved_trace_id)
    if error.code == ErrorType.MODEL_OUTPUT_CONTRACT.value:
        source = error.details or {}
        contract_details: JSONDict | None = None
        invalid_tool_json = source.get(
            "failure_type"
        ) == INVALID_TOOL_CALL_JSON_FAILURE_TYPE or is_invalid_tool_call_json_contract_error(
            message=error.message
        )
        if invalid_tool_json:
            message = "The model emitted malformed tool-call JSON."
            contract_details = {
                "failure_type": INVALID_TOOL_CALL_JSON_FAILURE_TYPE,
                "provider_detail": message,
            }
        else:
            message = (
                "The model returned invalid output. Retry the request or select a different model."
            )
        return ErrorPublicPayload(
            code=error.code,
            message=message,
            details=contract_details,
            trace_id=resolved_trace_id,
        )
    memory_message = resolve_memory_exhaustion_message(error.code)
    if memory_message is not None:
        return ErrorPublicPayload(
            code=error.code,
            message=memory_message,
            trace_id=resolved_trace_id,
        )
    failure_type = resolve_upstream_failure_type(error.details or {})
    if has_upstream_provider_marker(error) or failure_type is not None:
        try:
            provider_error_type = ErrorType(error.code)
        except ValueError:
            provider_error_type = resolve_execution_error_type_for_http_status(status_code)
        provider_payload = build_upstream_provider_public_error(
            error.details,
            error_type=provider_error_type,
            fallback_message="Upstream provider request failed.",
            trace_id=resolved_trace_id,
        )
        return (
            replace(provider_payload, http_status=status_code)
            if failure_type is None
            else provider_payload
        )
    if error.code == ErrorType.PLUGIN_UNAVAILABLE.value:
        return ErrorPublicPayload(
            code=error.code,
            message="Plugin backend became unavailable. Retry after recovery completes.",
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
    if status_code < 500 and isinstance(error, ApiError):
        return ErrorPublicPayload(
            code=error.code,
            message=error.message,
            details=error.details,
            trace_id=resolved_trace_id,
        )
    return None


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


def project_specific_public_exception(
    exception: BaseException,
    *,
    trace_id: str | None = None,
) -> ErrorPublicPayload | None:
    if isinstance(exception, SoAIError):
        return project_specific_public_error(exception, trace_id=trace_id)
    return None


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
