"""SoAI - Model parameter request override extraction [backend/core/models/parameter_request_overrides.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.models.context_parameter_mapping import (
    FIT_CONTEXT_PARAMETER_NAME,
    map_standardized_context_updates,
    resolve_context_parameter_name,
)
from core.types.json import JSONDict, JSONValue, is_json_value
from core.types.json_value import copy_json_value

__all__ = (
    "extract_payload_request_overrides",
    "is_request_overridable_parameter",
)


def is_request_overridable_parameter(definition: JSONValue) -> bool:
    if not isinstance(definition, dict):
        return False
    if definition.get("requires_reload"):
        return False
    if definition.get("request_overridable") is False:
        return False
    return definition.get("group") == "inference"


def extract_payload_request_overrides(
    *,
    payload: JSONDict | None,
    parameter_definitions: JSONDict,
) -> JSONDict:
    if not isinstance(payload, dict):
        return {}
    context_parameter_name = resolve_context_parameter_name(parameter_definitions)
    context_definition = (
        parameter_definitions.get(context_parameter_name)
        if context_parameter_name is not None
        else None
    )
    context_request_overridable = bool(
        isinstance(context_definition, dict)
        and context_definition.get("request_overridable") is not False
    )
    payload_without_direct_fit = {
        param_key: copy_json_value(param_value)
        for param_key, param_value in payload.items()
        if param_key != FIT_CONTEXT_PARAMETER_NAME and is_json_value(param_value)
    }
    mapped_payload = map_standardized_context_updates(
        payload_without_direct_fit,
        context_parameter_name,
        parameter_definitions,
    )
    request_overrides: JSONDict = {}
    for param_key, param_value in mapped_payload.items():
        if not is_json_value(param_value):
            continue
        definition = parameter_definitions.get(param_key)
        if param_key == context_parameter_name:
            if context_request_overridable:
                request_overrides[param_key] = copy_json_value(param_value)
            continue
        if param_key == FIT_CONTEXT_PARAMETER_NAME:
            fit_request_overridable = bool(
                isinstance(definition, dict) and definition.get("request_overridable") is not False
            )
            if context_request_overridable and fit_request_overridable:
                request_overrides[param_key] = copy_json_value(param_value)
            continue
        if is_request_overridable_parameter(definition):
            request_overrides[param_key] = copy_json_value(param_value)
    return request_overrides
