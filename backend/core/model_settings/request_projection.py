"""SoAI - Canonical Chat execution-settings request projection [backend/core/model_settings/request_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload
from core.models.context_window import MODEL_PARAM_STANDARDIZED_NAME
from core.types.json_value import copy_json_dict, copy_json_value
from core.validation.integers import is_positive_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "CONTEXT_WINDOW_OVERRIDE_CONFLICT_CODE",
    "CONTEXT_WINDOW_OVERRIDE_INVALID_CODE",
    "build_chat_execution_openai_request",
    "build_context_window_override_conflict_error",
    "read_execution_context_window_override",
    "require_context_window_override_value",
)

CONTEXT_WINDOW_OVERRIDE_INVALID_CODE = "context_window_override_invalid"
CONTEXT_WINDOW_OVERRIDE_CONFLICT_CODE = "context_window_override_conflict"

_NON_REQUEST_EXECUTION_FIELDS = frozenset(
    {
        "agent",
        "comparison_models",
        "identity",
        "prompts",
        "workspace_path",
    },
)


def _build_context_window_override_error(
    message: str,
    *,
    code: str,
    public_message: str,
) -> ValidationError:
    error = ValidationError(message)
    apply_public_error_payload(
        error,
        ErrorPublicPayload(
            code=code,
            message=public_message,
            param=MODEL_PARAM_STANDARDIZED_NAME,
            http_status=error.http_status,
        ),
    )
    return error


def build_context_window_override_conflict_error() -> ValidationError:
    return _build_context_window_override_error(
        "model_settings has conflicting context_window_tokens values.",
        code=CONTEXT_WINDOW_OVERRIDE_CONFLICT_CODE,
        public_message="The context window override has conflicting values. Set one value or clear the override, then retry.",
    )


def require_context_window_override_value(value: JSONValue) -> int:
    if not is_positive_strict_int(value):
        raise _build_context_window_override_error(
            "model_settings context_window_tokens must be a positive integer.",
            code=CONTEXT_WINDOW_OVERRIDE_INVALID_CODE,
            public_message="The context window override must be a positive whole number. Enter a valid value or leave it blank to use the model default.",
        )
    return int(value)


def _read_parameter_settings(model_settings: JSONDict) -> JSONDict:
    value = model_settings.get("parameters")
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("model_settings.parameters must be an object.")
    return copy_json_dict(value)


def build_chat_execution_openai_request(model_settings: JSONDict) -> JSONDict:
    request_json = copy_json_dict(model_settings)
    parameters = _read_parameter_settings(model_settings)
    if MODEL_PARAM_STANDARDIZED_NAME in model_settings:
        require_context_window_override_value(model_settings[MODEL_PARAM_STANDARDIZED_NAME])
    if MODEL_PARAM_STANDARDIZED_NAME in parameters:
        require_context_window_override_value(parameters[MODEL_PARAM_STANDARDIZED_NAME])
    request_json.pop("parameters", None)
    for field_name in _NON_REQUEST_EXECUTION_FIELDS:
        request_json.pop(field_name, None)
    for field_name, value in parameters.items():
        if field_name in request_json and request_json[field_name] != value:
            if field_name == MODEL_PARAM_STANDARDIZED_NAME:
                raise build_context_window_override_conflict_error()
            raise ValidationError(
                f"model_settings has conflicting values for '{field_name}'.",
            )
        request_json[field_name] = copy_json_value(value)
    return request_json


def read_execution_context_window_override(model_settings: JSONDict) -> int | None:
    request_json = build_chat_execution_openai_request(model_settings)
    if MODEL_PARAM_STANDARDIZED_NAME not in request_json:
        return None
    return require_context_window_override_value(request_json[MODEL_PARAM_STANDARDIZED_NAME])
