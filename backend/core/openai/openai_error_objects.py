"""SoAI - OpenAI error object helpers and parsers [backend/core/openai/openai_error_objects.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.openai.sse_frame_payloads import parse_openai_sse_frame_payloads
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_openai_error_object",
    "build_openai_error_payload",
    "coerce_openai_error_details_mapping",
    "extract_openai_error_fields_from_http_exception_detail",
    "extract_openai_error_fields_from_payload",
    "extract_openai_error_message_and_type_from_envelope",
    "normalize_openai_error_code_subtype",
    "parse_openai_http_exception_detail_message_and_type",
    "parse_openai_sse_error_frame",
    "parse_openai_sse_error_frame_message_and_type",
)


def build_openai_error_object(
    *,
    message: str,
    error_type: str,
    param: str | None,
    code: str | None,
) -> JSONDict:
    return {
        "message": str(message),
        "type": str(error_type),
        "param": param,
        "code": code,
    }


def extract_openai_error_fields_from_payload(
    payload: JSONValue,
) -> tuple[str | None, str | None, str | None]:
    if not isinstance(payload, dict):
        return (None, None, None)
    message_value = payload.get("message")
    error_type_value = payload.get("type")
    code_value = payload.get("code")
    message = message_value if isinstance(message_value, str) and message_value else None
    error_type = (
        error_type_value if isinstance(error_type_value, str) and error_type_value else None
    )
    code = code_value if isinstance(code_value, str) and code_value else None
    return (message, error_type, code)


def extract_openai_error_fields_from_http_exception_detail(
    detail: JSONValue,
) -> tuple[str, str | None, str | None, str | None]:
    detail_dict = coerce_json_dict(detail) or {}
    error_obj = coerce_json_dict(detail_dict.get("error")) or {}
    message_value = error_obj.get("message")
    message_text = message_value if isinstance(message_value, str) else str(detail)
    error_type_value = error_obj.get("type")
    error_type = (
        error_type_value if isinstance(error_type_value, str) and error_type_value else None
    )
    param_value = error_obj.get("param")
    code_value = error_obj.get("code")
    param = param_value if isinstance(param_value, str) and param_value else None
    code = code_value if isinstance(code_value, str) and code_value else None
    return (message_text, error_type, param, code)


def extract_openai_error_message_and_type_from_envelope(
    payload: JSONValue,
    *,
    fallback_message: str,
    fallback_error_type: str,
) -> tuple[str, str]:
    payload_dict = coerce_json_dict(payload)
    if payload_dict is None:
        return (fallback_message, fallback_error_type)
    error_payload = payload_dict.get("error")
    message, error_type, _code = extract_openai_error_fields_from_payload(error_payload)
    return (message or fallback_message, error_type or fallback_error_type)


def parse_openai_sse_error_frame(
    frame: bytes | str,
) -> tuple[str, str | None, str | None, str | None] | None:
    for payload in parse_openai_sse_frame_payloads(frame):
        error_obj = payload.get("error")
        message, error_type, code = extract_openai_error_fields_from_payload(error_obj)
        if message is None:
            continue
        return (message, error_type, None, code)
    return None


def parse_openai_sse_error_frame_message_and_type(frame: bytes | str) -> tuple[str, str] | None:
    parsed = parse_openai_sse_error_frame(frame)
    if parsed is None:
        return None
    message, error_type, _param, _code = parsed
    return (str(message), str(error_type or "server_error"))


def parse_openai_http_exception_detail_message_and_type(detail: JSONValue) -> tuple[str, str]:
    message_text, error_type, _param, _code = (
        extract_openai_error_fields_from_http_exception_detail(detail)
    )
    return (str(message_text), str(error_type or "server_error"))


def build_openai_error_payload(
    *,
    message: str,
    error_type: str,
    param: str | None = None,
    code: str | None = None,
) -> JSONDict:
    return {
        "error": build_openai_error_object(
            message=message,
            error_type=error_type,
            param=param,
            code=code,
        ),
    }


def normalize_openai_error_code_subtype(
    *,
    code: str | None,
    canonical_error_type: str,
) -> str | None:
    if not code:
        return None
    normalized = code.strip()
    if not normalized:
        return None
    if normalized == canonical_error_type:
        return None
    return normalized


def coerce_openai_error_details_mapping(
    details: Mapping[str, JSONValue] | None,
) -> Mapping[str, JSONValue]:
    if not isinstance(details, dict):
        return {}
    return details
