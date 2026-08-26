"""SoAI - Canonical Chat execution-settings request projection [backend/core/model_settings/request_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.models.context_window import MODEL_PARAM_STANDARDIZED_NAME
from core.types.json_value import copy_json_dict, copy_json_value
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_chat_execution_openai_request",
    "read_execution_context_window_override",
)

_NON_REQUEST_EXECUTION_FIELDS = frozenset(
    {
        "agent",
        "comparison_models",
        "identity",
        "prompts",
        "workspace_path",
    },
)


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
    request_json.pop("parameters", None)
    for field_name in _NON_REQUEST_EXECUTION_FIELDS:
        request_json.pop(field_name, None)
    for field_name, value in parameters.items():
        if field_name in request_json and request_json[field_name] != value:
            raise ValidationError(
                f"model_settings has conflicting values for '{field_name}'.",
            )
        request_json[field_name] = copy_json_value(value)
    return request_json


def read_execution_context_window_override(model_settings: JSONDict) -> int | None:
    request_json = build_chat_execution_openai_request(model_settings)
    if MODEL_PARAM_STANDARDIZED_NAME not in request_json:
        return None
    value = request_json[MODEL_PARAM_STANDARDIZED_NAME]
    if not is_strict_int(value) or value <= 0:
        raise ValidationError(
            "model_settings context_window_tokens must be a positive integer.",
        )
    return int(value)
