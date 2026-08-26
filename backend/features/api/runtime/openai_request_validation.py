"""SoAI - OpenAI API request validation boundary adapters [backend/features/api/runtime/openai_request_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.errors.exceptions import ValidationError
from core.openai.request_field_validation import (
    first_unknown_field,
    raise_required_string_field,
    raise_unsupported_field,
)
from core.openai.request_options import (
    extract_openai_bool_flag,
    extract_openai_store_flag,
    validate_openai_stream_options,
)
from features.api.openai.openai_error_responses import (
    build_openai_invalid_request_json_response,
)
from features.api.runtime.openai_error_conversion import (
    build_openai_validation_error_response,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_openai_invalid_request_response",
    "extract_openai_bool_flag_or_response",
    "extract_openai_store_flag_or_response",
    "extract_unknown_extra_fields",
    "reject_unknown_openai_fields",
    "require_openai_string_field_or_response",
    "validate_openai_stream_options_or_response",
)


def extract_unknown_extra_fields(payload: BaseModel) -> tuple[str, ...]:
    try:
        extra = payload.__pydantic_extra__
    except AttributeError:
        extra = None
    if not isinstance(extra, dict) or not extra:
        return ()
    keys: list[str] = []
    for key in extra:
        if isinstance(key, str) and key:
            keys.append(key)
    if not keys:
        return ()
    return tuple(sorted(keys))


def build_openai_invalid_request_response(
    *,
    message: str,
    param: str | None,
    trace_id: str,
    status_code: int = 400,
    code: str | None = None,
) -> JSONResponse:
    return build_openai_invalid_request_json_response(
        status_code=status_code,
        message=message,
        param=param,
        code=code,
        trace_id=trace_id,
        headers=None,
    )


def extract_openai_bool_flag_or_response(
    payload_json: dict[str, JSONValue],
    *,
    key: str,
    default: bool,
    trace_id: str,
    invalid_message: str,
) -> tuple[bool, JSONResponse | None]:
    try:
        return (
            extract_openai_bool_flag(
                payload_json,
                key=key,
                default=default,
                trace_id=trace_id,
            ),
            None,
        )
    except ValidationError:
        return (
            bool(default),
            build_openai_invalid_request_response(
                message=invalid_message,
                param=str(key),
                trace_id=trace_id,
            ),
        )


def extract_openai_store_flag_or_response(
    payload_json: dict[str, JSONValue],
    *,
    default: bool,
    trace_id: str,
    invalid_message: str,
) -> tuple[bool, JSONResponse | None]:
    try:
        return (
            extract_openai_store_flag(
                payload_json,
                default=default,
                trace_id=trace_id,
            ),
            None,
        )
    except ValidationError:
        return (
            bool(default),
            build_openai_invalid_request_response(
                message=invalid_message,
                param="store",
                trace_id=trace_id,
            ),
        )


def validate_openai_stream_options_or_response(
    payload_json: JSONDict,
    *,
    trace_id: str,
    allow_include_usage: bool,
) -> JSONResponse | None:
    try:
        validate_openai_stream_options(
            payload_json,
            trace_id=trace_id,
            allow_include_usage=allow_include_usage,
        )
        return None
    except ValidationError as exception:
        return build_openai_validation_error_response(exception, trace_id=trace_id)


def reject_unknown_openai_fields(
    payload_json: dict[str, JSONValue],
    *,
    allowed_fields: frozenset[str],
    trace_id: str,
) -> JSONResponse | None:
    field_name = first_unknown_field(payload_json, allowed_fields=allowed_fields)
    if field_name is None:
        return None
    try:
        raise_unsupported_field(field_name, trace_id=trace_id)
    except ValidationError as exception:
        return build_openai_validation_error_response(exception, trace_id=trace_id)


def require_openai_string_field_or_response(
    payload_json: dict[str, JSONValue],
    *,
    field_name: str,
    trace_id: str,
) -> str | JSONResponse:
    try:
        field_value = raise_required_string_field(
            payload_json,
            field_name=field_name,
            trace_id=trace_id,
        )
    except ValidationError as exception:
        return build_openai_validation_error_response(exception, trace_id=trace_id)
    return field_value
