"""SoAI - OpenAI API key authentication response helpers [backend/features/api/openai/api_key_auth.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from core.runtime.request_trace_id import get_request_trace_id
from features.api.openai.openai_error_responses import build_openai_error_json_response
from features.api.runtime.openai_request_state import resolve_openai_api_key_id_optional

__all__ = ("require_openai_api_key_id",)


def require_openai_api_key_id(request: Request) -> str | JSONResponse:
    api_key_id = resolve_openai_api_key_id_optional(request)
    if api_key_id is None:
        return build_openai_error_json_response(
            status_code=401,
            message="You are not authenticated.",
            canonical_error_type="authentication_error",
            param=None,
            code=None,
            trace_id=get_request_trace_id(request),
            headers=None,
        )
    return api_key_id
