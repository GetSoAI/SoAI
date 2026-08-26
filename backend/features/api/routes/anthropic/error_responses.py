"""SoAI - Anthropic API error responses [backend/features/api/routes/anthropic/error_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from starlette.responses import JSONResponse, Response

from core.openai.openai_error_objects import (
    extract_openai_error_message_and_type_from_envelope,
)
from core.system_api.anthropic_error_types import resolve_anthropic_error_type
from core.types.json import JSONDict
from features.api.runtime.response_body import parse_response_body_json_dict

__all__ = (
    "build_anthropic_error_response",
    "project_error_response",
)


def build_anthropic_error_response(
    *,
    status_code: int,
    message: str,
    error_type: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"type": "error", "error": {"type": error_type, "message": message}},
        headers=headers,
    )


def project_error_response(response: Response) -> Response:
    if response.status_code < 400:
        return response
    payload: JSONDict = parse_response_body_json_dict(response, field="OpenAI error response")
    message, upstream_error_type = extract_openai_error_message_and_type_from_envelope(
        payload,
        fallback_message="Request failed.",
        fallback_error_type="invalid_request_error",
    )
    headers = {
        name: value
        for name, value in response.headers.items()
        if name.lower()
        in {"retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"}
    }
    return build_anthropic_error_response(
        status_code=response.status_code,
        message=message,
        error_type=resolve_anthropic_error_type(
            status_code=response.status_code,
            upstream_error_type=upstream_error_type,
        ),
        headers=headers or None,
    )
