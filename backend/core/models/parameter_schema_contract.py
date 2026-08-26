"""SoAI - Shared V1 model parameter schema contracts [backend/core/models/parameter_schema_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json import is_json_dict, is_json_list, is_json_value
from core.validation.integers import is_strict_int
from core.validation.record_fields import require_number
from core.validation.strict_numbers import require_positive_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "validate_parameter_definition",
    "validate_parameter_definitions",
    "validate_parameter_value",
)

_PARAMETER_TYPES = frozenset(("string", "integer", "float", "boolean", "array", "object"))


def _error(message: str) -> ValidationError:
    return ValidationError(message)


def _require_finite_number(value: JSONValue, label: str) -> int | float:
    return require_number(
        value,
        label=label,
        build_error=_error,
        invalid_message=f"{label} must be a finite number.",
        finite_message=f"{label} must be a finite number.",
    )


def _require_bound(value: JSONValue, parameter_type: str, label: str) -> int | float:
    number = _require_finite_number(value, label)
    if parameter_type == "integer" and not is_strict_int(number):
        raise ValidationError(f"{label} must be an integer.")
    return number


def _read_bounds(
    definition: JSONDict, parameter_type: str, label: str
) -> tuple[int | float | None, int | float | None]:
    range_present = "range" in definition
    range_value = definition.get("range")
    range_minimum: int | float | None = None
    range_maximum: int | float | None = None
    if range_present:
        if not is_json_list(range_value) or len(range_value) != 2:
            raise ValidationError(f"{label}.range must contain exactly two numbers.")
        range_minimum = _require_bound(range_value[0], parameter_type, f"{label}.range[0]")
        range_maximum = _require_bound(range_value[1], parameter_type, f"{label}.range[1]")
    minimum = (
        _require_bound(definition.get("minimum"), parameter_type, f"{label}.minimum")
        if "minimum" in definition
        else range_minimum
    )
    maximum = (
        _require_bound(definition.get("maximum"), parameter_type, f"{label}.maximum")
        if "maximum" in definition
        else range_maximum
    )
    if range_minimum is not None and minimum != range_minimum:
        raise ValidationError(f"{label}.range and minimum contradict each other.")
    if range_maximum is not None and maximum != range_maximum:
        raise ValidationError(f"{label}.range and maximum contradict each other.")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValidationError(f"{label} minimum must not exceed maximum.")
    return (minimum, maximum)


def _json_values_equal(left: JSONValue, right: JSONValue) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, int | float) and isinstance(right, int | float):
        return left == right
    return type(left) is type(right) and left == right


def _read_enum(definition: JSONDict, label: str) -> list[JSONValue] | None:
    enum_present = "enum" in definition
    choices_present = "choices" in definition
    enum_value = definition.get("enum")
    choices_value = definition.get("choices")
    if enum_present and not is_json_list(enum_value):
        raise ValidationError(f"{label}.enum must be an array.")
    if choices_present and not is_json_list(choices_value):
        raise ValidationError(f"{label}.choices must be an array.")
    if isinstance(enum_value, list) and isinstance(choices_value, list):
        if len(enum_value) != len(choices_value) or any(
            not _json_values_equal(enum_item, choice_item)
            for enum_item, choice_item in zip(enum_value, choices_value, strict=True)
        ):
            raise ValidationError(f"{label}.enum and choices contradict each other.")
    resolved = enum_value if isinstance(enum_value, list) else choices_value
    if not isinstance(resolved, list):
        return None
    if not resolved:
        raise ValidationError(f"{label} enum must not be empty.")
    for item_index, item in enumerate(resolved):
        if not is_json_value(item) or isinstance(item, list | dict) or item is None:
            raise ValidationError(f"{label} enum item {item_index} must be a JSON scalar.")
        if any(_json_values_equal(item, previous) for previous in resolved[:item_index]):
            raise ValidationError(f"{label} enum contains duplicate values.")
    return list(resolved)


def _matches_type(value: JSONValue, parameter_type: str) -> bool:
    if parameter_type == "integer":
        return is_strict_int(value)
    if parameter_type == "float":
        return (
            isinstance(value, int | float) and not isinstance(value, bool) and is_json_value(value)
        )
    if parameter_type == "boolean":
        return isinstance(value, bool)
    if parameter_type == "string":
        return isinstance(value, str)
    if parameter_type == "array":
        return is_json_list(value)
    if parameter_type == "object":
        return is_json_dict(value)
    return False


def _validate_enum_items(enum_values: list[JSONValue] | None, value_type: str, label: str) -> None:
    if enum_values is None:
        return
    for item_index, item in enumerate(enum_values):
        if not _matches_type(item, value_type):
            raise ValidationError(
                f"{label} enum item {item_index} does not match type '{value_type}'.",
            )


def _read_numeric_string_bounds(
    definition: JSONDict, label: str
) -> tuple[Decimal | None, Decimal | None]:
    minimum = None
    if "numeric_string_minimum" in definition:
        minimum_number = _require_finite_number(
            definition.get("numeric_string_minimum"),
            f"{label}.numeric_string_minimum",
        )
        minimum = Decimal(str(minimum_number))
    maximum = None
    if "numeric_string_maximum" in definition:
        maximum_number = _require_finite_number(
            definition.get("numeric_string_maximum"),
            f"{label}.numeric_string_maximum",
        )
        maximum = Decimal(str(maximum_number))
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValidationError(f"{label} numeric-string minimum must not exceed maximum.")
    return (minimum, maximum)


def _parse_numeric_string(value: str, label: str) -> Decimal:
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation as exception:
        raise ValidationError(f"{label} must be a finite numeric string.") from exception
    if not parsed.is_finite():
        raise ValidationError(f"{label} must be a finite numeric string.")
    return parsed


def _value_in_enum(value: JSONValue, enum_values: list[JSONValue] | None) -> bool:
    return enum_values is not None and any(_json_values_equal(value, item) for item in enum_values)


def validate_parameter_definition(parameter_name: str, definition: JSONDict) -> None:
    label = f"Parameter '{parameter_name}'"
    parameter_type_value = definition.get("type")
    if not isinstance(parameter_type_value, str) or parameter_type_value not in _PARAMETER_TYPES:
        raise ValidationError(f"{label} has an invalid type.")
    parameter_type = parameter_type_value
    enum_values = _read_enum(definition, label)
    if parameter_type in {"integer", "float"}:
        _read_bounds(definition, parameter_type, label)
    elif any(field_name in definition for field_name in ("range", "minimum", "maximum")):
        raise ValidationError(f"{label} numeric bounds require an integer or float type.")
    numeric_string_bounds = _read_numeric_string_bounds(definition, label)
    if parameter_type != "string" and numeric_string_bounds != (None, None):
        raise ValidationError(f"{label} numeric-string bounds require a string type.")
    if parameter_type == "array":
        item_type = definition.get("item_type")
        if not isinstance(item_type, str) or item_type not in _PARAMETER_TYPES:
            raise ValidationError(f"{label}.item_type is invalid.")
        _validate_enum_items(enum_values, item_type, label)
        if "value_count" in definition:
            require_positive_int_strict(
                definition.get("value_count"),
                error_message=f"{label}.value_count must be a positive integer.",
            )
    else:
        if "item_type" in definition or "value_count" in definition:
            raise ValidationError(f"{label} array metadata requires an array type.")
        _validate_enum_items(enum_values, parameter_type, label)
    has_default = definition.get("has_default")
    if not isinstance(has_default, bool):
        raise ValidationError(f"{label}.has_default must be a boolean.")
    if has_default != ("default" in definition):
        raise ValidationError(f"{label}.has_default contradicts default presence.")
    if has_default:
        validate_parameter_value(
            definition=definition,
            value=definition.get("default"),
            label=f"{label}.default",
        )


def validate_parameter_definitions(definitions: JSONDict) -> None:
    for parameter_name, definition_value in definitions.items():
        if not isinstance(parameter_name, str) or not parameter_name.strip():
            raise ValidationError("Parameter names must be non-empty strings.")
        if not is_json_dict(definition_value):
            raise ValidationError(f"Parameter '{parameter_name}' definition must be an object.")
        validate_parameter_definition(parameter_name, definition_value)


def validate_parameter_value(*, definition: JSONDict, value: JSONValue, label: str) -> None:
    parameter_type_value = definition.get("type")
    if not isinstance(parameter_type_value, str) or parameter_type_value not in _PARAMETER_TYPES:
        raise ValidationError(f"{label} has an invalid schema type.")
    parameter_type = parameter_type_value
    if not _matches_type(value, parameter_type):
        raise ValidationError(f"{label} must have type '{parameter_type}'.")
    enum_values = _read_enum(definition, label)
    if parameter_type == "array":
        if not isinstance(value, list):
            raise ValidationError(f"{label} must be an array.")
        item_type_value = definition.get("item_type")
        if not isinstance(item_type_value, str) or item_type_value not in _PARAMETER_TYPES:
            raise ValidationError(f"{label} has an invalid item_type.")
        for item_index, item in enumerate(value):
            if not _matches_type(item, item_type_value):
                raise ValidationError(
                    f"{label}[{item_index}] must have type '{item_type_value}'.",
                )
            if enum_values is not None and not _value_in_enum(item, enum_values):
                raise ValidationError(f"{label}[{item_index}] is not an allowed value.")
        value_count = definition.get("value_count")
        if value_count is not None and len(value) != value_count:
            raise ValidationError(f"{label} must contain exactly {value_count} values.")
        return
    if parameter_type in {"integer", "float"}:
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise ValidationError(f"{label} must be numeric.")
        minimum, maximum = _read_bounds(definition, parameter_type, label)
        if minimum is not None and value < minimum:
            raise ValidationError(f"{label} is below the minimum value {minimum}.")
        if maximum is not None and value > maximum:
            raise ValidationError(f"{label} exceeds the maximum value {maximum}.")
    if parameter_type == "string":
        if not isinstance(value, str):
            raise ValidationError(f"{label} must be a string.")
        numeric_minimum, numeric_maximum = _read_numeric_string_bounds(definition, label)
        if (numeric_minimum is not None or numeric_maximum is not None) and not _value_in_enum(
            value,
            enum_values,
        ):
            numeric_value = _parse_numeric_string(value, label)
            if numeric_minimum is not None and numeric_value < numeric_minimum:
                raise ValidationError(f"{label} is below its numeric-string minimum.")
            if numeric_maximum is not None and numeric_value > numeric_maximum:
                raise ValidationError(f"{label} exceeds its numeric-string maximum.")
            return
    if enum_values is not None and not _value_in_enum(value, enum_values):
        raise ValidationError(f"{label} is not an allowed value.")
