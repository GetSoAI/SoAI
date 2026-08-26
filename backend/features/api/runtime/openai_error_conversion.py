"""SoAI - OpenAI API error response conversion [backend/features/api/runtime/openai_error_conversion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Never

from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from core.errors.exceptions import SoAIError, ValidationError
from core.errors.public_projection import project_public_error
from core.errors.soai_error_http_fields import extract_soai_error_http_fields
from core.openai.openai_error_objects import (
    extract_openai_error_fields_from_http_exception_detail,
)
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response_for_soai_payload,
    build_openai_error_json_response_for_status,
    build_openai_invalid_request_json_response,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "build_openai_http_exception_response",
    "build_openai_internal_error_response",
    "build_openai_soai_error_response",
    "build_openai_validation_error_response",
    "raise_openai_bad_request",
)


def _extract_param(details: Mapping[str, JSONValue] | None) -> str | None:
    if details is None:
        return None
    param_value = details.get("param")
    if isinstance(param_value, str) and param_value:
        return param_value
    return None


def build_openai_validation_error_response(
    exception: ValidationError,
    *,
    trace_id: str | None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    public_payload = project_public_error(exception, trace_id=trace_id)
    return build_openai_invalid_request_json_response(
        message=public_payload.message,
        param=_extract_param(public_payload.details),
        trace_id=trace_id,
        headers=headers,
    )


def build_openai_http_exception_response(
    exception: HTTPException,
    *,
    trace_id: str | None,
) -> JSONResponse:
    if exception.status_code >= 500:
        return build_openai_error_json_response_for_status(
            status_code=exception.status_code,
            message="Internal server error.",
            soai_code=None,
            param=None,
            trace_id=trace_id,
            headers=exception.headers,
        )
    message, _error_type, param, code = extract_openai_error_fields_from_http_exception_detail(
        exception.detail,
    )
    return build_openai_error_json_response_for_status(
        status_code=exception.status_code,
        message=message,
        soai_code=code,
        param=param,
        trace_id=trace_id,
        headers=exception.headers,
    )


def build_openai_soai_error_response(
    exception: SoAIError,
    *,
    trace_id: str | None,
) -> JSONResponse:
    http_status, _details, _soai_code, headers = extract_soai_error_http_fields(exception)
    public_payload = project_public_error(exception, trace_id=trace_id)
    return build_openai_error_json_response_for_soai_payload(
        status_code=http_status,
        message=public_payload.message,
        soai_error_type=public_payload.code,
        details=public_payload.details,
        trace_id=trace_id,
        headers=headers,
    )


def build_openai_internal_error_response(*, trace_id: str | None) -> JSONResponse:
    return build_openai_error_json_response_for_status(
        status_code=500,
        message="Internal server error.",
        soai_code=None,
        param=None,
        trace_id=trace_id,
        headers=None,
    )


def raise_openai_bad_request(message: str, *, cause: BaseException | None = None) -> Never:
    raise HTTPException(status_code=400, detail=message) from cause
