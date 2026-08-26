"""SoAI - HTTP error decoding helpers [backend/core/errors/http_error_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import httpx2

from core.errors.exceptions import ValidationError
from core.network.http_json import read_http_json_dict

__all__ = (
    "extract_http_response_message",
    "extract_text_from_response",
)


def extract_http_response_message(response: httpx2.Response, status_code: int) -> str:
    default_message = f"HTTP {status_code} error"
    try:
        body = read_http_json_dict(response, field="HTTP error response")
        error_obj = body.get("error")
        if isinstance(error_obj, dict):
            message = error_obj.get("message")
            if isinstance(message, str) and message:
                return message
        if isinstance(error_obj, str) and error_obj:
            return error_obj
        message = body.get("message")
        if isinstance(message, str) and message:
            return message
        detail = body.get("detail")
        if isinstance(detail, str) and detail:
            return detail
    except (
        ValidationError,
        ValueError,
        TypeError,
        httpx2.ResponseNotRead,
        httpx2.StreamClosed,
        OSError,
        RuntimeError,
    ):
        return extract_text_from_response(response, default_message)
    return default_message


def extract_text_from_response(response: httpx2.Response, default_message: str) -> str:
    try:
        text = response.text
        if text:
            return text[:500] if len(text) > 500 else text
    except (
        UnicodeDecodeError,
        AttributeError,
        TypeError,
        httpx2.ResponseNotRead,
        httpx2.StreamClosed,
        OSError,
        RuntimeError,
    ):
        return default_message
    return default_message
