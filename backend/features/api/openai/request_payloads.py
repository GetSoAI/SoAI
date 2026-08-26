"""SoAI - OpenAI request payload parsing [backend/features/api/openai/request_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from starlette.responses import Response

from core.errors.exceptions import StateError, ValidationError
from core.serialization.json_parsing import parse_json_value
from core.validation.http_headers import content_type_is_json
from features.api.openai.openai_error_responses import (
    build_openai_invalid_request_json_response,
)
from features.api.runtime.request_media_types import require_non_multipart_media_type
from features.api.runtime.request_payloads import read_json_dict_payload

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "parse_json_object_body",
    "parse_object_body_json_or_form",
)


async def parse_json_object_body(
    request: Request,
    *,
    trace_id: str,
) -> dict[str, JSONValue] | Response:
    try:
        payload = await read_json_dict_payload(
            request,
            invalid_json_message="Request body must be valid JSON.",
            invalid_object_message="Request body must be a JSON object.",
            normalization_error_message="Request body must be a JSON object.",
        )
    except ValidationError as exception:
        return build_openai_invalid_request_json_response(
            message=str(exception),
            param=None,
            trace_id=trace_id,
        )
    except StateError:
        return build_openai_invalid_request_json_response(
            message="Request body must be a JSON object.",
            param=None,
            trace_id=trace_id,
        )
    return payload


async def parse_object_body_json_or_form(
    request: Request,
    *,
    trace_id: str,
) -> dict[str, JSONValue] | Response:
    try:
        require_non_multipart_media_type(request)
    except ValidationError as exception:
        return build_openai_invalid_request_json_response(
            message=str(exception),
            param=None,
            trace_id=trace_id,
        )
    content_type = request.headers.get("content-type") or ""
    normalized_content_type = str(content_type or "").lower()
    if "application/x-www-form-urlencoded" in normalized_content_type:
        try:
            form = await request.form()
        except ValueError:
            return build_openai_invalid_request_json_response(
                message="Request body must be valid form data.",
                param=None,
                trace_id=trace_id,
            )
        payload: dict[str, JSONValue] = {}
        for key, value in form.multi_items():
            if not isinstance(key, str) or not key:
                continue
            if isinstance(value, str | int | float) and not isinstance(value, bool):
                payload[key] = str(value) if not isinstance(value, str) else value
        input_value = payload.get("input")
        if isinstance(input_value, str):
            stripped = input_value.strip()
            if stripped.startswith("[") or stripped.startswith("{"):
                try:
                    decoded = parse_json_value(stripped)
                except (TypeError, ValueError, ValidationError):
                    decoded = None
                if decoded is not None:
                    payload["input"] = decoded
        return payload
    if normalized_content_type and (not content_type_is_json(normalized_content_type)):
        return build_openai_invalid_request_json_response(
            message="Content-Type must be application/json or application/x-www-form-urlencoded.",
            param=None,
            trace_id=trace_id,
        )
    return await parse_json_object_body(request, trace_id=trace_id)
