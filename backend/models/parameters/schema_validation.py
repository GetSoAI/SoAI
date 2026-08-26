"""SoAI - Model parameter schema validation helpers [backend/models/parameters/schema_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.models.context_parameter_mapping import (
    map_standardized_context_keys,
    map_standardized_context_updates,
    resolve_context_parameter_name,
)
from core.models.parameter_schema_contract import validate_parameter_value
from core.openai.upstream_request_customization import (
    validate_openai_request_customization_parameter,
)
from core.types.json import JSONDict

__all__ = (
    "validate_parameter_keys_exist",
    "validate_parameter_values",
)


def validate_parameter_values(
    *,
    plugin_name: str,
    schema: JSONDict,
    parameters: JSONDict,
) -> None:
    context_parameter_name = resolve_context_parameter_name(schema)
    normalized_parameters = map_standardized_context_updates(
        parameters,
        context_parameter_name,
        schema,
    )
    for key, value in normalized_parameters.items():
        definition_value = schema.get(key)
        if not isinstance(definition_value, dict):
            raise ValidationError(f"Invalid parameter '{key}' for plugin '{plugin_name}'.")
        validate_openai_request_customization_parameter(key, value)
        if value is None:
            continue
        validate_parameter_value(
            definition=definition_value,
            value=value,
            label=f"Parameter '{key}' for plugin '{plugin_name}'",
        )


def validate_parameter_keys_exist(
    *,
    plugin_name: str,
    schema: JSONDict,
    keys: list[str],
) -> None:
    context_parameter_name = resolve_context_parameter_name(schema)
    normalized_keys = map_standardized_context_keys(keys, context_parameter_name, schema)
    bad_keys = set(normalized_keys) - set(schema.keys())
    if bad_keys:
        raise ValidationError(
            f"Invalid parameter keys for '{plugin_name}': {', '.join(sorted(bad_keys))}",
        )
