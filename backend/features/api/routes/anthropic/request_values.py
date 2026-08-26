"""SoAI - Anthropic request value validation [backend/features/api/routes/anthropic/request_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import HTTPException

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue
from core.validation.json_schema import validate_json_schema

__all__ = (
    "invalid_anthropic_request",
    "require_anthropic_dict",
    "require_anthropic_json_schema",
    "require_anthropic_text",
    "require_anthropic_trimmed_string",
)


def invalid_anthropic_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def require_anthropic_dict(value: JSONValue, field: str) -> JSONDict:
    if not isinstance(value, dict):
        raise invalid_anthropic_request(f"{field} must be an object.")
    return value


def require_anthropic_text(value: JSONValue, field: str) -> str:
    if not isinstance(value, str) or value == "":
        raise invalid_anthropic_request(f"{field} must be a non-empty string.")
    return value


def require_anthropic_trimmed_string(value: JSONValue, field: str) -> str:
    text = require_anthropic_text(value, field)
    if not text.strip():
        raise invalid_anthropic_request(f"{field} must not contain only whitespace.")
    return text


def require_anthropic_json_schema(value: JSONValue, field: str) -> JSONDict:
    schema = require_anthropic_dict(value, field)
    try:
        validate_json_schema(schema)
    except ValidationError as exception:
        raise invalid_anthropic_request(f"{field} must be a valid JSON Schema.") from exception
    return schema
