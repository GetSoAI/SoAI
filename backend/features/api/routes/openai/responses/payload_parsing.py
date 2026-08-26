"""SoAI - Shared OpenAI Responses payload parsing helpers [backend/features/api/routes/openai/responses/payload_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.responses import Response

from core.types.json import is_json_list
from features.api.openai.openai_error_responses import build_openai_error_json_response
from features.api.runtime.openai_request_validation import (
    reject_unknown_openai_fields,
    require_openai_string_field_or_response,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "parse_optional_responses_input_value_or_response",
    "require_responses_model_known_fields",
)


def require_responses_model_known_fields(
    payload_json: dict[str, JSONValue],
    *,
    allowed_fields: frozenset[str],
    trace_id: str,
) -> str | Response:
    unknown_fields_error = reject_unknown_openai_fields(
        payload_json,
        allowed_fields=allowed_fields,
        trace_id=trace_id,
    )
    if unknown_fields_error is not None:
        return unknown_fields_error
    return require_openai_string_field_or_response(
        payload_json,
        field_name="model",
        trace_id=trace_id,
    )


def parse_optional_responses_input_value_or_response(
    payload_json: dict[str, JSONValue],
    *,
    trace_id: str,
) -> str | list[JSONValue] | None | Response:
    if "input" not in payload_json:
        return None
    input_value = payload_json["input"]
    if isinstance(input_value, str):
        return input_value
    if is_json_list(input_value):
        return input_value
    return build_openai_error_json_response(
        status_code=400,
        message="input must be a string or array.",
        canonical_error_type="invalid_request_error",
        param="input",
        code=None,
        trace_id=trace_id,
        headers=None,
    )
