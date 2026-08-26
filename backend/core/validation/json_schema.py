"""SoAI - JSON Schema validation boundary [backend/core/validation/json_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from jsonschema import exceptions, validators
from referencing.exceptions import Unresolvable

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict

__all__ = ("validate_json_schema", "validate_json_schema_instance")


def _validate_json_schema(schema: JSONDict, instance: JSONDict | None) -> None:
    try:
        validator_class = validators.validator_for(schema)
        validator_class.check_schema(schema)
        if instance is not None:
            validator_class(schema).validate(instance)
    except exceptions.SchemaError as exception:
        raise ValidationError("JSON Schema is invalid.") from exception
    except exceptions.ValidationError as exception:
        raise ValidationError(
            "Generated JSON does not satisfy the requested schema."
        ) from exception
    except Unresolvable as exception:
        raise ValidationError("JSON Schema reference could not be resolved.") from exception


def validate_json_schema(schema: JSONDict) -> None:
    _validate_json_schema(schema, None)


def validate_json_schema_instance(instance: JSONDict, schema: JSONDict) -> None:
    _validate_json_schema(schema, instance)
