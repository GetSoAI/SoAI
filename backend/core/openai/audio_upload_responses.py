"""SoAI - OpenAI audio upload response envelope helpers [backend/core/openai/audio_upload_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "AUDIO_UPLOAD_ERROR_RESPONSE_MARKER",
    "build_audio_upload_error_response",
    "is_audio_upload_error_response",
    "read_audio_upload_error_response",
    "resolve_audio_upload_raw_media_type",
)

AUDIO_UPLOAD_ERROR_RESPONSE_MARKER = "soai_audio_upload_error_response_v1"
_SUPPORTED_RESPONSE_FORMATS = frozenset(("text", "srt", "vtt"))


def build_audio_upload_error_response(
    *,
    status_code: int,
    error_type: str,
    message: str,
    param: str | None = None,
) -> JSONDict:
    if status_code < 400 or status_code > 599:
        raise ValidationError("Audio upload error status_code must be a 4xx or 5xx value.")
    normalized_type = error_type.strip()
    normalized_message = message.strip()
    if not normalized_type:
        raise ValidationError("Audio upload error_type is required.")
    if not normalized_message:
        raise ValidationError("Audio upload error message is required.")
    error_payload: JSONDict = {
        "type": normalized_type,
        "code": normalized_type,
        "message": normalized_message,
        "param": param,
    }
    return {
        "soai_response_type": AUDIO_UPLOAD_ERROR_RESPONSE_MARKER,
        "status_code": status_code,
        "error": error_payload,
    }


def resolve_audio_upload_raw_media_type(response_format: str) -> str:
    normalized_format = response_format.strip().lower()
    if normalized_format not in _SUPPORTED_RESPONSE_FORMATS:
        raise ValidationError("Unsupported raw audio response_format.")
    if normalized_format == "text":
        return "text/plain; charset=utf-8"
    if normalized_format == "srt":
        return "application/x-subrip; charset=utf-8"
    return "text/vtt; charset=utf-8"


def is_audio_upload_error_response(payload: JSONValue) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("soai_response_type") == AUDIO_UPLOAD_ERROR_RESPONSE_MARKER
    )


def read_audio_upload_error_response(payload: JSONValue) -> tuple[int, JSONDict]:
    if not isinstance(payload, dict) or not is_audio_upload_error_response(payload):
        raise ValidationError("Audio upload error envelope marker is missing.")
    status_code_value = payload.get("status_code")
    if not is_strict_int(status_code_value):
        raise ValidationError("Audio upload error status_code must be an integer.")
    if status_code_value < 400 or status_code_value > 599:
        raise ValidationError("Audio upload error status_code must be a 4xx or 5xx value.")
    error_value = payload.get("error")
    if not isinstance(error_value, dict):
        raise ValidationError("Audio upload error payload is missing.")
    message_value = error_value.get("message")
    type_value = error_value.get("type")
    if not isinstance(type_value, str) or not type_value.strip():
        raise ValidationError("Audio upload error type is missing.")
    if not isinstance(message_value, str) or not message_value.strip():
        raise ValidationError("Audio upload error message is missing.")
    return status_code_value, dict(error_value)
