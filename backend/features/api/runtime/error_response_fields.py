"""SoAI - API JSON error response field extraction [backend/features/api/runtime/error_response_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi.responses import JSONResponse

from core.errors.error_types import ErrorType
from core.errors.exceptions import ValidationError
from core.openai.openai_error_objects import (
    extract_openai_error_message_and_type_from_envelope,
)
from features.api.runtime.response_body import parse_response_body_json_value

__all__ = ("extract_error_fields_from_response",)


def extract_error_fields_from_response(
    response: JSONResponse,
    *,
    fallback_message: str = "Internal server error.",
    fallback_error_type: str = ErrorType.SERVER_ERROR.value,
) -> tuple[str, str]:
    try:
        response_payload = parse_response_body_json_value(response, field="error response body")
    except (TypeError, ValidationError):
        return (fallback_message, fallback_error_type)
    return extract_openai_error_message_and_type_from_envelope(
        response_payload,
        fallback_message=fallback_message,
        fallback_error_type=fallback_error_type,
    )
