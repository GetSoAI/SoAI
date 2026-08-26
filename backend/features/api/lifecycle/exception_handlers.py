"""SoAI - Exception handler definitions and registration for FastAPI application [backend/features/api/lifecycle/exception_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.logging.trace import get_logger
from core.system_api.request_paths import (
    get_scope_path,
    is_anthropic_api_request_path,
    is_openai_api_request_path,
    is_openai_compatibility_request_path,
)
from features.api.lifecycle.rate_limiting_config import (
    handle_rate_limit_exceeded,
)
from features.api.middleware.openai_response_metadata import (
    apply_anthropic_response_metadata_headers,
    apply_openai_response_metadata_headers,
)
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response_for_status,
)
from features.api.rate_limiting.rate_limit_evaluator import ApiRateLimitExceeded
from features.api.routes.anthropic.error_responses import build_anthropic_error_response
from features.api.runtime.boundary_error_responses import (
    build_boundary_error_json_response_for_soai_error,
    build_boundary_http_exception_json_response,
    build_boundary_request_validation_json_response,
    build_coerced_json_error_response,
    build_soai_error_json_response_for_status,
)
from features.api.runtime.context import get_request_trace_id

__all__ = (
    "handle_http_exception",
    "handle_request_validation_error",
    "handle_soai_error",
    "handle_unhandled_exception",
    "register_exception_handlers",
)

LOGGER_NAME = "SoAI.features.api.exception_handlers"
OPERATION = "api_lifecycle.unhandled_exception"


async def handle_soai_error(request: Request, exception: Exception) -> JSONResponse:
    trace_id = get_request_trace_id(request)
    coerced = (
        exception
        if isinstance(exception, SoAIError)
        else coerce_to_soai_error(exception, trace_id=trace_id)
    )
    return build_boundary_error_json_response_for_soai_error(
        request,
        coerced,
        trace_id=trace_id,
    )


async def handle_http_exception(request: Request, exception: Exception) -> JSONResponse:
    trace_id = get_request_trace_id(request)
    if not isinstance(exception, HTTPException):
        return build_coerced_json_error_response(
            exception,
            trace_id=trace_id,
            operation="api_lifecycle.http_exception",
        )
    return build_boundary_http_exception_json_response(
        request,
        exception,
        trace_id=trace_id,
    )


async def handle_request_validation_error(request: Request, exception: Exception) -> JSONResponse:
    trace_id = get_request_trace_id(request)
    return build_boundary_request_validation_json_response(
        request,
        exception,
        trace_id=trace_id,
    )


_GENERIC_INTERNAL_ERROR_MESSAGE = "Internal server error."


async def handle_unhandled_exception(request: Request, exception: Exception) -> JSONResponse:
    path = get_scope_path(request.scope)
    trace_id = get_request_trace_id(request)
    coerced = coerce_to_soai_error(
        exception,
        trace_id=trace_id,
        operation="api_lifecycle.unhandled_exception",
    )
    log_exception(
        get_logger(LOGGER_NAME),
        coerced,
        message="Unhandled exception in API handler.",
        trace_id=trace_id,
        operation=OPERATION,
        level="error",
    )
    if is_anthropic_api_request_path(path):
        response = build_anthropic_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=_GENERIC_INTERNAL_ERROR_MESSAGE,
            error_type="api_error",
        )
    elif is_openai_api_request_path(path):
        response = build_openai_error_json_response_for_status(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=_GENERIC_INTERNAL_ERROR_MESSAGE,
            soai_code=None,
            param=None,
            trace_id=trace_id,
            headers=None,
        )
    else:
        response = build_soai_error_json_response_for_status(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=_GENERIC_INTERNAL_ERROR_MESSAGE,
            soai_code="server_error",
            trace_id=trace_id,
        )
    if is_anthropic_api_request_path(path):
        apply_anthropic_response_metadata_headers(request.scope, response.headers)
    elif is_openai_compatibility_request_path(path):
        apply_openai_response_metadata_headers(request.scope, response.headers)
    return response


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(SoAIError, handle_soai_error)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(ApiRateLimitExceeded, handle_rate_limit_exceeded)
    app.add_exception_handler(Exception, handle_unhandled_exception)
