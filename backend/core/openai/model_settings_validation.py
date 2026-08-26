"""SoAI - OpenAI model settings validation helper [backend/core/openai/model_settings_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.model_settings.normalization import normalize_model_selection_settings
from core.openai.output_token_cap import canonicalize_model_settings_output_token_cap
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONDict, JSONValue
from core.validation.record_fields import require_number

__all__ = ("validate_model_settings",)


def validate_model_settings(settings: JSONValue | str) -> JSONDict:
    if settings is None:
        raise ValidationError("Model settings are required.")
    if isinstance(settings, str):
        if not settings.strip():
            raise ValidationError("Model settings must be a JSON object.")
        try:
            settings = parse_json_value(settings)
        except ValidationError as exception:
            raise ValidationError(f"Model settings must be valid JSON: {exception}") from exception
    if not isinstance(settings, dict):
        raise ValidationError(f"Model settings must be a dict, got {type(settings).__name__}.")
    validated: JSONDict = {}
    known_numeric_params = {
        "temperature",
        "top_p",
        "max_tokens",
        "max_completion_tokens",
        "max_output_tokens",
        "n",
        "frequency_penalty",
        "presence_penalty",
        "top_logprobs",
        "seed",
        "timeout",
    }
    known_boolean_params = {
        "stream",
        "logprobs",
        "parallel_tool_calls",
        "echo",
        "store",
        "reasoning_effort_send_enabled",
        "max_completion_tokens_send_enabled",
        "top_p_send_enabled",
        "frequency_penalty_send_enabled",
        "presence_penalty_send_enabled",
        "stop_send_enabled",
        "logprobs_send_enabled",
    }
    known_object_params = {
        "logit_bias",
        "response_format",
        "json_schema",
        "tool_choice",
        "stream_options",
        "metadata",
        "prediction",
        "audio",
        "web_search_options",
        "reasoning",
    }
    known_array_params = {"stop", "tools", "modalities", "include"}
    known_string_params = {
        "model",
        "user",
        "suffix",
        "encoding_format",
        "reasoning_effort",
        "service_tier",
        "instructions",
        "previous_response_id",
        "truncation",
    }
    for key, value in settings.items():
        if not isinstance(key, str):
            raise ValidationError(f"Model setting key must be string, got {type(key).__name__}.")
        if key in known_numeric_params:
            if value is not None:
                require_number(
                    value,
                    label=f"Model setting '{key}'",
                    build_error=ValidationError,
                    invalid_message=(
                        f"Model setting '{key}' must be numeric, got {type(value).__name__}."
                    ),
                )
        elif key in known_boolean_params:
            if not isinstance(value, bool | type(None)):
                raise ValidationError(
                    f"Model setting '{key}' must be boolean, got {type(value).__name__}.",
                )
        elif key in known_object_params:
            if value is not None and (not isinstance(value, dict)):
                raise ValidationError(
                    f"Model setting '{key}' must be an object, got {type(value).__name__}.",
                )
        elif key in known_array_params:
            if value is not None and (not isinstance(value, list | str)):
                raise ValidationError(
                    f"Model setting '{key}' must be array or string, got {type(value).__name__}.",
                )
        elif key in known_string_params:
            if value is not None and (not isinstance(value, str)):
                raise ValidationError(
                    f"Model setting '{key}' must be string, got {type(value).__name__}.",
                )
        validated[key] = value
    return canonicalize_model_settings_output_token_cap(
        normalize_model_selection_settings(validated),
    )
