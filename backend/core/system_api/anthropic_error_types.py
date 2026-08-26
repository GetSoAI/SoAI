"""SoAI - Anthropic API error type resolution [backend/core/system_api/anthropic_error_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("resolve_anthropic_error_type",)


def resolve_anthropic_error_type(
    *,
    status_code: int | None = None,
    upstream_error_type: str | None = None,
) -> str:
    if status_code == 401:
        return "authentication_error"
    if status_code == 403:
        return "permission_error"
    if status_code == 404:
        return "not_found_error"
    if status_code == 413:
        return "request_too_large"
    if status_code == 429:
        return "rate_limit_error"
    if status_code == 529:
        return "overloaded_error"
    if status_code is not None and status_code >= 500:
        return "api_error"
    if status_code is not None:
        return "invalid_request_error"
    match upstream_error_type:
        case "authentication_error" | "invalid_api_key":
            return "authentication_error"
        case "invalid_request_error":
            return "invalid_request_error"
        case "not_found_error":
            return "not_found_error"
        case "overloaded_error":
            return "overloaded_error"
        case "permission_error":
            return "permission_error"
        case "rate_limit_error":
            return "rate_limit_error"
        case "request_too_large":
            return "request_too_large"
        case _:
            return "api_error"
