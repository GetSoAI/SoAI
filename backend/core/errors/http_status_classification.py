"""SoAI - Canonical HTTP status classification [backend/core/errors/http_status_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from core.errors.error_types import ErrorType

__all__ = (
    "resolve_execution_error_type_for_http_status",
    "resolve_openai_error_type_for_http_status",
    "resolve_openai_http_status_for_error",
    "resolve_probe_status_for_http_status",
    "resolve_soai_error_code_for_http_status",
)


def resolve_soai_error_code_for_http_status(status_code: int) -> str:
    match int(status_code):
        case 400 | 405 | 413 | 415 | 422:
            return ErrorType.INVALID_REQUEST.value
        case 401:
            return ErrorType.AUTHENTICATION_ERROR.value
        case 403:
            return ErrorType.FORBIDDEN.value
        case 404:
            return ErrorType.NOT_FOUND.value
        case 409:
            return ErrorType.CONFLICT.value
        case 429:
            return ErrorType.RATE_LIMIT.value
        case 500:
            return ErrorType.SERVER_ERROR.value
        case 503:
            return ErrorType.SERVICE_UNAVAILABLE.value
        case _:
            if int(status_code) >= 500:
                return ErrorType.SERVER_ERROR.value
            return ErrorType.INVALID_REQUEST.value


def resolve_openai_error_type_for_http_status(status_code: int) -> str:
    match int(status_code):
        case 401:
            return ErrorType.AUTHENTICATION_ERROR.value
        case 403:
            return "permission_error"
        case 404:
            return ErrorType.NOT_FOUND.value
        case 429:
            return ErrorType.RATE_LIMIT.value
        case 500 | 501 | 502 | 503 | 504:
            return ErrorType.SERVER_ERROR.value
        case _:
            if int(status_code) >= 500:
                return ErrorType.SERVER_ERROR.value
            return ErrorType.INVALID_REQUEST.value


def resolve_openai_http_status_for_error(*, status_code: int, error_type: str) -> int:
    if int(status_code) == 422 and str(error_type) == ErrorType.INVALID_REQUEST.value:
        return 400
    return int(status_code)


def resolve_execution_error_type_for_http_status(status_code: int) -> ErrorType:
    match int(status_code):
        case 400 | 415 | 422:
            return ErrorType.INVALID_REQUEST
        case 401 | 403:
            return ErrorType.AUTHENTICATION_ERROR
        case 404:
            return ErrorType.NOT_FOUND
        case 409:
            return ErrorType.CONFLICT
        case 423:
            return ErrorType.LOCKED
        case 429:
            return ErrorType.OVERLOADED
        case 500 | 502:
            return ErrorType.SERVER_ERROR
        case 503:
            return ErrorType.PLUGIN_UNAVAILABLE
        case 504:
            return ErrorType.TIMEOUT_ERROR
        case _:
            if int(status_code) >= 500:
                return ErrorType.SERVER_ERROR
            return ErrorType.INVALID_REQUEST


def resolve_probe_status_for_http_status(
    status_code: int | None,
) -> Literal[
    "present",
    "missing",
    "auth_failed",
    "rate_limited",
    "server_error",
    "invalid_request",
    "network_error",
]:
    if status_code is None:
        return "network_error"
    normalized_status = int(status_code)
    if normalized_status == 404:
        return "missing"
    if normalized_status in (401, 403):
        return "auth_failed"
    if normalized_status == 429:
        return "rate_limited"
    if normalized_status >= 500:
        return "server_error"
    if normalized_status in (400, 405, 415, 422):
        return "invalid_request"
    return "present"
