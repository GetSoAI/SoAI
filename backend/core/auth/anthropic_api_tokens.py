"""SoAI - Anthropic API token extraction [backend/core/auth/anthropic_api_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.auth.jwt_tokens import extract_bearer_token
from core.errors.exceptions import ApiError
from core.runtime.protocols import RequestProtocol

__all__ = ("extract_anthropic_api_token",)


def extract_anthropic_api_token(request: RequestProtocol) -> str | None:
    bearer_value = (extract_bearer_token(request.headers.get("Authorization")) or "").strip()
    api_key_value = (request.headers.get("x-api-key") or "").strip()
    if bearer_value and api_key_value and bearer_value != api_key_value:
        raise ApiError(
            "Authorization and x-api-key credentials must match.",
            code="invalid_request_error",
            http_status=400,
            operation="core.auth.anthropic_api_tokens.extract_anthropic_api_token",
        )
    return bearer_value or api_key_value or None
