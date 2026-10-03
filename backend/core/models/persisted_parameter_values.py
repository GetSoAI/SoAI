"""SoAI - Schema-owned decoding of persisted model parameters [backend/core/models/persisted_parameter_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.models.parameter_schema_contract import (
    read_legacy_string_separator,
    validate_parameter_value,
)
from core.types.json import JSONDict, JSONValue
from core.types.json_value import copy_json_dict

__all__ = ("decode_persisted_parameter_values", "resolve_effective_parameter_values")


def decode_persisted_parameter_values(schema: JSONDict, values: JSONDict) -> JSONDict:
    decoded = copy_json_dict(values)
    for name, value in values.items():
        definition = schema.get(name)
        if not isinstance(definition, dict) or not isinstance(value, str):
            continue
        separator = read_legacy_string_separator(definition, name)
        if separator is None:
            continue
        converted: list[JSONValue] = [item.strip() for item in value.split(separator)]
        try:
            validate_parameter_value(definition=definition, value=converted, label=name)
        except ValidationError as exception:
            exception.public_message = (
                "A saved model parameter cannot be converted to its current format. "
                "Update or reset the indicated parameter and retry."
            )
            exception.public_details = {"parameter": name}
            raise
        decoded[name] = converted
    return decoded


def resolve_effective_parameter_values(schema: JSONDict, values: JSONDict) -> JSONDict:
    effective: JSONDict = {
        name: definition.get("default")
        for name, definition in schema.items()
        if isinstance(definition, dict) and definition.get("has_default", "default" in definition)
    }
    effective.update(decode_persisted_parameter_values(schema, values))
    return copy_json_dict(effective)
