"""SoAI - OpenAI upstream request field customization [backend/core/openai/upstream_request_customization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue, is_json_dict
from core.types.json_value import copy_json_dict

__all__ = (
    "SOAI_INTERNAL_OPENAI_REQUEST_KEYS",
    "SOAI_OPENAI_CUSTOM_REQUEST_FIELDS_PARAMETER",
    "SOAI_OPENAI_EXCLUDED_REQUEST_FIELDS_PARAMETER",
    "OpenAIUpstreamRequestCustomization",
    "build_openai_request_customization_schema_additions",
    "resolve_openai_upstream_request_customization",
    "summarize_openai_request_customization_for_log",
    "validate_openai_request_customization_parameter",
)

SOAI_OPENAI_CUSTOM_REQUEST_FIELDS_PARAMETER = "soai_openai_custom_request_fields"
SOAI_OPENAI_EXCLUDED_REQUEST_FIELDS_PARAMETER = "soai_openai_excluded_request_fields"

SOAI_INTERNAL_OPENAI_REQUEST_KEYS = frozenset(
    {
        "_request_type",
        "_responses_operation",
        "conv_id",
        "context_length",
        "mcp",
        "required_capabilities",
        "responses_api",
        "soai_chat_template_max_role",
        SOAI_OPENAI_CUSTOM_REQUEST_FIELDS_PARAMETER,
        SOAI_OPENAI_EXCLUDED_REQUEST_FIELDS_PARAMETER,
    },
)

_PROTECTED_REQUEST_FIELDS = (
    *SOAI_INTERNAL_OPENAI_REQUEST_KEYS,
    "file",
    "image",
    "image_temp_path",
    "image_temp_paths",
    "input",
    "mask",
    "mask_temp_path",
    "messages",
    "model",
    "original_filename",
    "original_filenames",
    "prompt",
    "stream",
    "temp_file_path",
)


@dataclass(frozen=True, slots=True)
class OpenAIUpstreamRequestCustomization:
    custom_fields: JSONDict
    excluded_fields: frozenset[str]


def build_openai_request_customization_schema_additions() -> tuple[JSONDict, JSONDict]:
    parameters: JSONDict = {
        SOAI_OPENAI_EXCLUDED_REQUEST_FIELDS_PARAMETER: {
            "group": "inference",
            "aliases": [],
            "has_default": False,
            "description": (
                "OpenAI request fields to omit for this model when the upstream provider "
                "rejects specific fields."
            ),
            "type": "array",
            "item_type": "string",
            "category": "compatibility",
            "requires_reload": False,
            "request_overridable": False,
        },
        SOAI_OPENAI_CUSTOM_REQUEST_FIELDS_PARAMETER: {
            "group": "inference",
            "aliases": [],
            "has_default": False,
            "description": (
                "Additional OpenAI-compatible upstream request fields and values for this model. "
                "Custom fields override ordinary request and model parameter values."
            ),
            "type": "object",
            "category": "compatibility",
            "requires_reload": False,
            "request_overridable": False,
        },
    }
    categories: JSONDict = {
        "compatibility": {
            "title": "Compatibility",
            "description": "Settings that adapt requests for backend and provider compatibility.",
        },
    }
    return parameters, categories


def _require_request_field_name(value: str, *, parameter_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{parameter_name} entries must be non-empty strings.")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValidationError(f"{parameter_name} entries must not contain control characters.")
    if normalized in _PROTECTED_REQUEST_FIELDS:
        raise ValidationError(
            f"{parameter_name} cannot target SoAI-owned request field '{normalized}'.",
        )
    return normalized


def _normalize_excluded_request_fields(value: JSONValue) -> frozenset[str]:
    if value is None:
        return frozenset()
    if not isinstance(value, list):
        raise ValidationError(
            f"{SOAI_OPENAI_EXCLUDED_REQUEST_FIELDS_PARAMETER} must be an array of strings.",
        )
    normalized_fields: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValidationError(
                f"{SOAI_OPENAI_EXCLUDED_REQUEST_FIELDS_PARAMETER} entries must be strings.",
            )
        normalized_fields.add(
            _require_request_field_name(
                item,
                parameter_name=SOAI_OPENAI_EXCLUDED_REQUEST_FIELDS_PARAMETER,
            ),
        )
    return frozenset(normalized_fields)


def validate_openai_request_customization_parameter(
    parameter_name: str,
    value: JSONValue,
) -> None:
    if parameter_name == SOAI_OPENAI_CUSTOM_REQUEST_FIELDS_PARAMETER:
        if value is None:
            return
        if not is_json_dict(value):
            raise ValidationError(
                f"{SOAI_OPENAI_CUSTOM_REQUEST_FIELDS_PARAMETER} must be a JSON object.",
            )
        for field_name in value:
            normalized = _require_request_field_name(
                field_name,
                parameter_name=SOAI_OPENAI_CUSTOM_REQUEST_FIELDS_PARAMETER,
            )
            if normalized != field_name:
                raise ValidationError(
                    f"{SOAI_OPENAI_CUSTOM_REQUEST_FIELDS_PARAMETER} field names must not have surrounding whitespace.",
                )
        return
    if parameter_name == SOAI_OPENAI_EXCLUDED_REQUEST_FIELDS_PARAMETER:
        _normalize_excluded_request_fields(value)


def resolve_openai_upstream_request_customization(
    model_parameters: JSONDict,
) -> OpenAIUpstreamRequestCustomization:
    custom_value = model_parameters.get(SOAI_OPENAI_CUSTOM_REQUEST_FIELDS_PARAMETER)
    excluded_value = model_parameters.get(SOAI_OPENAI_EXCLUDED_REQUEST_FIELDS_PARAMETER)
    validate_openai_request_customization_parameter(
        SOAI_OPENAI_CUSTOM_REQUEST_FIELDS_PARAMETER,
        custom_value,
    )
    validate_openai_request_customization_parameter(
        SOAI_OPENAI_EXCLUDED_REQUEST_FIELDS_PARAMETER,
        excluded_value,
    )
    custom_fields = copy_json_dict(custom_value) if isinstance(custom_value, dict) else {}
    excluded_fields = _normalize_excluded_request_fields(excluded_value)
    return OpenAIUpstreamRequestCustomization(
        custom_fields=custom_fields,
        excluded_fields=excluded_fields,
    )


def summarize_openai_request_customization_for_log(value: JSONValue) -> str:
    if not isinstance(value, dict):
        return "[custom request field values redacted]"
    field_names = sorted(str(field_name) for field_name in value)[:10]
    rendered_names = ", ".join(repr(field_name[:64]) for field_name in field_names)
    extra_count = len(value) - len(field_names)
    suffix = f", ... (+{extra_count})" if extra_count > 0 else ""
    return f"{len(value)} field(s), values redacted: {rendered_names}{suffix}"
