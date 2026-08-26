"""SoAI - Boundary JSON error responses for API surfaces [backend/features/api/runtime/boundary_error_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exceptions import SoAIError
from core.errors.http_status_classification import (
    resolve_soai_error_code_for_http_status,
)
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import project_public_error
from core.errors.soai_error_http_fields import extract_soai_error_http_fields
from core.system_api.anthropic_error_types import resolve_anthropic_error_type
from core.system_api.request_paths import (
    get_scope_path,
    is_anthropic_api_request_path,
    is_openai_api_request_path,
)
from core.types.json_value import coerce_json_dict
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response_for_status,
)
from features.api.routes.anthropic.error_responses import build_anthropic_error_response
from features.api.runtime.context import get_request_trace_id
from features.api.runtime.openai_error_conversion import (
    build_openai_http_exception_response,
    build_openai_soai_error_response,
)
from features.api.runtime.request_validation_errors import (
    extract_request_validation_message_and_param,
)
from features.api.runtime.response_body import create_json_body_response

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "build_boundary_error_json_response_for_request",
    "build_boundary_error_json_response_for_soai_error",
    "build_boundary_http_exception_json_response",
    "build_boundary_request_validation_json_response",
    "build_coerced_json_error_response",
    "build_soai_error_json_response",
    "build_soai_error_json_response_for_status",
)


def build_boundary_error_json_response_for_request(
    request: Request,
    *,
    status_code: int,
    message: str,
    soai_code: str,
    openai_code: str | int | None = None,
    param: str | None = None,
    details: Mapping[str, JSONValue] | None = None,
    headers: Mapping[str, str] | None = None,
    trace_id: str | None = None,
) -> JSONResponse:
    response_trace_id = trace_id or get_request_trace_id(request)
    response_headers = dict(headers) if headers is not None else None
    request_path = get_scope_path(request.scope)
    if is_anthropic_api_request_path(request_path):
        return build_anthropic_error_response(
            status_code=status_code,
            message=message,
            error_type=resolve_anthropic_error_type(status_code=status_code),
            headers=response_headers,
        )
    if is_openai_api_request_path(request_path):
        return build_openai_error_json_response_for_status(
            status_code=status_code,
            message=message,
            soai_code=str(openai_code) if openai_code is not None else None,
            param=param,
            trace_id=response_trace_id,
            headers=response_headers,
        )
    return _create_public_soai_error_json_response(
        status_code=status_code,
        payload=ErrorPublicPayload(
            code=soai_code,
            message=message,
            details=details,
            trace_id=response_trace_id,
        ),
        headers=response_headers,
    )


def build_boundary_error_json_response_for_soai_error(
    request: Request,
    coerced: SoAIError,
    *,
    trace_id: str | None,
) -> JSONResponse:
    request_path = get_scope_path(request.scope)
    if is_anthropic_api_request_path(request_path):
        status_code = coerced.http_status or 500
        return build_anthropic_error_response(
            status_code=status_code,
            message=("Internal server error." if status_code >= 500 else coerced.message),
            error_type=resolve_anthropic_error_type(status_code=status_code),
        )
    if is_openai_api_request_path(request_path):
        return build_openai_soai_error_response(coerced, trace_id=trace_id)
    return build_soai_error_json_response(coerced, trace_id=trace_id)


def build_boundary_http_exception_json_response(
    request: Request,
    exception: HTTPException,
    *,
    trace_id: str | None,
) -> JSONResponse:
    request_path = get_scope_path(request.scope)
    if is_anthropic_api_request_path(request_path):
        message = str(exception.detail or "Request failed.")
        return build_anthropic_error_response(
            status_code=exception.status_code,
            message="Internal server error." if exception.status_code >= 500 else message,
            error_type=resolve_anthropic_error_type(status_code=exception.status_code),
            headers=dict(exception.headers) if exception.headers is not None else None,
        )
    if is_openai_api_request_path(request_path):
        return build_openai_http_exception_response(exception, trace_id=trace_id)
    if exception.status_code >= 500:
        return build_soai_error_json_response_for_status(
            status_code=exception.status_code,
            message="Internal server error.",
            soai_code="server_error",
            trace_id=trace_id,
            headers=exception.headers,
        )
    message = "Request failed."
    details: Mapping[str, JSONValue] | None = None
    error_type = resolve_soai_error_code_for_http_status(exception.status_code)
    detail = exception.detail
    if isinstance(detail, dict):
        error_payload = detail.get("error")
        if isinstance(error_payload, dict):
            message = str(error_payload.get("message") or message)
            error_type = str(error_payload.get("type") or error_type)
            details = coerce_json_dict(error_payload.get("details"))
        else:
            message = str(detail.get("message") or message)
            error_type = str(detail.get("type") or error_type)
            details = coerce_json_dict(detail.get("details"))
    elif detail:
        message = str(detail)
    return build_soai_error_json_response_for_status(
        status_code=exception.status_code,
        message=message,
        soai_code=error_type,
        details=details,
        trace_id=trace_id,
        headers=exception.headers,
    )


def build_boundary_request_validation_json_response(
    request: Request,
    exception: Exception,
    *,
    trace_id: str | None,
) -> JSONResponse:
    request_path = get_scope_path(request.scope)
    if is_anthropic_api_request_path(request_path):
        message = "Request validation failed."
        if isinstance(exception, RequestValidationError):
            message, _param = extract_request_validation_message_and_param(exception)
        return build_anthropic_error_response(
            status_code=400,
            message=message,
            error_type="invalid_request_error",
        )
    if is_openai_api_request_path(request_path):
        param: str | None = None
        message = "Request validation failed."
        if isinstance(exception, RequestValidationError):
            message, param = extract_request_validation_message_and_param(exception)
        return build_openai_error_json_response_for_status(
            status_code=400,
            message=message,
            soai_code=None,
            param=param,
            trace_id=trace_id,
            headers=None,
        )
    details = (
        {"validation_errors": _sanitize_validation_errors(exception)}
        if isinstance(exception, RequestValidationError)
        else None
    )
    return build_soai_error_json_response_for_status(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        message="Request validation failed.",
        soai_code="invalid_request_error",
        details=details,
        trace_id=trace_id,
    )


def _sanitize_validation_errors(exception: RequestValidationError) -> list[JSONValue]:
    sanitized: list[JSONValue] = []
    for error in exception.errors():
        entry: dict[str, JSONValue] = {}
        error_type = error.get("type")
        location = error.get("loc")
        message = error.get("msg")
        if isinstance(error_type, str):
            entry["type"] = error_type
        if isinstance(location, tuple | list):
            entry["loc"] = [str(segment) for segment in location]
        if isinstance(message, str):
            entry["msg"] = message
        sanitized.append(entry)
    return sanitized


def build_soai_error_json_response_for_status(
    *,
    status_code: int,
    message: str,
    soai_code: str,
    details: Mapping[str, JSONValue] | None = None,
    trace_id: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    if status_code >= 500:
        message = "Internal server error."
        details = None
    return _create_public_soai_error_json_response(
        status_code=status_code,
        payload=ErrorPublicPayload(
            code=soai_code,
            message=message,
            details=details,
            trace_id=trace_id,
        ),
        headers=headers,
    )


def _create_public_soai_error_json_response(
    *,
    status_code: int,
    payload: ErrorPublicPayload,
    headers: Mapping[str, str] | None,
) -> JSONResponse:
    return create_json_body_response(
        status_code=status_code,
        content={"error": payload.to_dict()},
        headers=headers,
        no_store=True,
    )


def build_coerced_json_error_response(
    exception: Exception,
    *,
    trace_id: str | None,
    operation: str,
) -> JSONResponse:
    coerced = coerce_to_soai_error(
        exception,
        trace_id=trace_id,
        operation=operation,
    )
    return build_soai_error_json_response(coerced, trace_id=trace_id)


def build_soai_error_json_response(
    coerced: SoAIError,
    *,
    trace_id: str | None,
) -> JSONResponse:
    public_payload = project_public_error(coerced, trace_id=trace_id)
    status_code, _details, _soai_code, headers = extract_soai_error_http_fields(coerced)
    return _create_public_soai_error_json_response(
        status_code=status_code,
        payload=public_payload,
        headers=headers,
    )
