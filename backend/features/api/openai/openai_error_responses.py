"""SoAI - OpenAI /v1 error response builders [backend/features/api/openai/openai_error_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from core.errors.http_status_classification import (
    resolve_openai_error_type_for_http_status,
    resolve_openai_http_status_for_error,
)
from core.errors.payload import ErrorPublicPayload
from core.openai.openai_error_objects import (
    build_openai_error_payload,
    normalize_openai_error_code_subtype,
)
from core.openai.request_requirement_failures import (
    classify_openai_request_requirement_mismatch,
)
from core.timing.retry_backoff import normalize_retry_after_header
from features.api.runtime.response_body import create_json_body_response
from features.api.runtime.responses import apply_operation_id_header

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "build_openai_error_json_response",
    "build_openai_error_json_response_for_soai_payload",
    "build_openai_error_json_response_for_status",
    "build_openai_invalid_request_json_response",
)


def build_openai_error_json_response(
    *,
    status_code: int,
    message: str,
    canonical_error_type: str,
    param: str | None,
    code: str | None,
    trace_id: str | None,
    headers: Mapping[str, str] | None = None,
    message_is_public: bool = False,
) -> JSONResponse:
    resolved_status_code = int(status_code)
    if resolved_status_code >= 500 and not message_is_public:
        message = "Internal server error."
        canonical_error_type = "server_error"
        param = None
        code = code or "internal_error"
    response = create_json_body_response(
        status_code=resolved_status_code,
        content=build_openai_error_payload(
            message=message,
            error_type=canonical_error_type,
            param=param,
            code=normalize_openai_error_code_subtype(
                code=code,
                canonical_error_type=canonical_error_type,
            ),
        ),
        no_store=True,
    )
    if headers:
        for key, value in headers.items():
            if key.lower() == "retry-after":
                retry_after = normalize_retry_after_header(value)
                if retry_after is not None:
                    response.headers[key] = retry_after
            else:
                response.headers[str(key)] = str(value)
    if trace_id and "X-SoAI-Operation-Id" not in response.headers:
        apply_operation_id_header(response, trace_id)
    return response


def build_openai_error_json_response_for_status(
    *,
    status_code: int,
    message: str,
    soai_code: str | int | None,
    param: str | None,
    trace_id: str | None,
    headers: Mapping[str, str] | None = None,
    message_is_public: bool = False,
) -> JSONResponse:
    canonical_error_type = resolve_openai_error_type_for_http_status(int(status_code))
    effective_status = resolve_openai_http_status_for_error(
        status_code=int(status_code),
        error_type=canonical_error_type,
    )
    code_text = str(soai_code) if soai_code is not None else None
    return build_openai_error_json_response(
        status_code=effective_status,
        message=message,
        canonical_error_type=canonical_error_type,
        param=param,
        code=code_text,
        trace_id=trace_id,
        headers=headers,
        message_is_public=message_is_public,
    )


def build_openai_invalid_request_json_response(
    *,
    message: str,
    param: str | None,
    trace_id: str | None,
    status_code: int = 400,
    code: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return build_openai_error_json_response(
        status_code=status_code,
        message=message,
        canonical_error_type="invalid_request_error",
        param=param,
        code=code,
        trace_id=trace_id,
        headers=headers,
    )


def build_openai_error_json_response_for_soai_payload(
    *,
    status_code: int,
    message: str,
    soai_error_type: str | int | None,
    details: Mapping[str, JSONValue] | None,
    trace_id: str | None,
    headers: Mapping[str, str] | None = None,
    public_error: ErrorPublicPayload | None = None,
) -> JSONResponse:
    param = public_error.param if public_error is not None else None
    if public_error is not None:
        status_code = public_error.http_status or status_code
        message = public_error.message
        soai_error_type = public_error.code
        details = public_error.details
        trace_id = public_error.trace_id or trace_id
    elif isinstance(details, dict):
        param_value = details.get("param")
        if isinstance(param_value, str) and param_value.strip():
            param = param_value.strip()
    response_headers = dict(headers or {})
    retry_value = details.get("retry_after") if details is not None else None
    retry_after = normalize_retry_after_header(
        retry_value if isinstance(retry_value, str) else None
    )
    if retry_after is not None:
        response_headers["Retry-After"] = retry_after
    if (
        public_error is not None
        and public_error.http_status == 422
        and classify_openai_request_requirement_mismatch(
            message=None, details=dict(details) if details is not None else None
        )
        is not None
    ):
        return build_openai_invalid_request_json_response(
            status_code=422,
            message=message,
            param=param,
            code=str(soai_error_type) if soai_error_type is not None else None,
            trace_id=trace_id,
            headers=response_headers,
        )
    return build_openai_error_json_response_for_status(
        status_code=int(status_code),
        message=message,
        soai_code=soai_error_type,
        param=param,
        trace_id=trace_id,
        headers=response_headers,
        message_is_public=True,
    )
