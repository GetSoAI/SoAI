"""SoAI - MCP temperature, length, weight, and data conversion tool [backend/mcp/tools/unit_conversion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_unit_convert",)

_ALLOWED_KEYS: frozenset[str] = frozenset({"value", "from_unit", "to_unit", "category"})


def _build_temp_units() -> dict[str, str]:
    return {
        "c": "celsius",
        "celsius": "celsius",
        "f": "fahrenheit",
        "fahrenheit": "fahrenheit",
        "k": "kelvin",
        "kelvin": "kelvin",
    }


def _build_length_units() -> dict[str, float]:
    return {
        "m": 1.0,
        "meter": 1.0,
        "meters": 1.0,
        "km": 1000.0,
        "kilometer": 1000.0,
        "kilometers": 1000.0,
        "cm": 0.01,
        "centimeter": 0.01,
        "centimeters": 0.01,
        "mm": 0.001,
        "millimeter": 0.001,
        "millimeters": 0.001,
        "mi": 1609.344,
        "mile": 1609.344,
        "miles": 1609.344,
        "yd": 0.9144,
        "yard": 0.9144,
        "yards": 0.9144,
        "ft": 0.3048,
        "foot": 0.3048,
        "feet": 0.3048,
        "in": 0.0254,
        "inch": 0.0254,
        "inches": 0.0254,
    }


def _build_weight_units() -> dict[str, float]:
    return {
        "kg": 1.0,
        "kilogram": 1.0,
        "kilograms": 1.0,
        "g": 0.001,
        "gram": 0.001,
        "grams": 0.001,
        "mg": 1e-06,
        "milligram": 1e-06,
        "milligrams": 1e-06,
        "lb": 0.453592,
        "pound": 0.453592,
        "pounds": 0.453592,
        "oz": 0.0283495,
        "ounce": 0.0283495,
        "ounces": 0.0283495,
        "t": 1000.0,
        "ton": 1000.0,
        "tonne": 1000.0,
    }


def _build_data_units() -> dict[str, int]:
    return {
        "b": 1,
        "byte": 1,
        "bytes": 1,
        "kb": 1024,
        "kilobyte": 1024,
        "kilobytes": 1024,
        "mb": 1024**2,
        "megabyte": 1024**2,
        "megabytes": 1024**2,
        "gb": 1024**3,
        "gigabyte": 1024**3,
        "gigabytes": 1024**3,
        "tb": 1024**4,
        "terabyte": 1024**4,
        "terabytes": 1024**4,
        "pb": 1024**5,
        "petabyte": 1024**5,
        "petabytes": 1024**5,
    }


async def tool_unit_convert(
    _utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    value = get_arg(arguments, "value")
    from_unit_raw = get_arg(arguments, "from_unit")
    to_unit_raw = get_arg(arguments, "to_unit")
    if not isinstance(from_unit_raw, str):
        raise MCPToolError(
            -32602,
            f"Parameter 'from_unit' must be a string, got {type(from_unit_raw).__name__}",
        )
    if not isinstance(to_unit_raw, str):
        raise MCPToolError(
            -32602,
            f"Parameter 'to_unit' must be a string, got {type(to_unit_raw).__name__}",
        )
    from_unit = from_unit_raw.lower()
    to_unit = to_unit_raw.lower()
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MCPToolError(
            -32602,
            f"Parameter 'value' must be a number, got {type(value).__name__}",
        )
    category_raw = arguments.get("category")
    if category_raw is not None and (not isinstance(category_raw, str)):
        raise MCPToolError(
            -32602,
            f"Parameter 'category' must be a string, got {type(category_raw).__name__}",
        )
    category = category_raw.lower() if category_raw else None
    result, detected_category = _perform_conversion(value, from_unit, to_unit, category)
    return {
        "result": result,
        "from_value": value,
        "from_unit": from_unit,
        "to_unit": to_unit,
        "category": detected_category,
        "expression": f"{value} {from_unit} = {result} {to_unit}",
    }


def _perform_conversion(
    value: float,
    from_unit: str,
    to_unit: str,
    category: str | None,
) -> tuple[float, str]:
    temp_units = _build_temp_units()
    length_units = _build_length_units()
    weight_units = _build_weight_units()
    data_units = _build_data_units()
    if category == "temperature" or (
        not category and from_unit in temp_units and (to_unit in temp_units)
    ):
        return _convert_temperature(value, from_unit, to_unit, temp_units), "temperature"
    if category == "length" or (
        not category and from_unit in length_units and (to_unit in length_units)
    ):
        return _convert_length(value, from_unit, to_unit, length_units), "length"
    if category == "weight" or (
        not category and from_unit in weight_units and (to_unit in weight_units)
    ):
        return _convert_weight(value, from_unit, to_unit, weight_units), "weight"
    if category == "data" or (not category and from_unit in data_units and (to_unit in data_units)):
        return _convert_data(value, from_unit, to_unit, data_units), "data"
    raise MCPToolError(
        -32602,
        f"Cannot convert from '{from_unit}' to '{to_unit}'. Specify category or use valid units.",
    )


def _convert_temperature(
    value: float,
    from_unit: str,
    to_unit: str,
    temp_units: dict[str, str],
) -> float:
    if from_unit not in temp_units or to_unit not in temp_units:
        raise MCPToolError(
            -32602,
            "Invalid temperature unit. Valid: c, f, k (celsius, fahrenheit, kelvin)",
        )
    from_t, to_t = (temp_units[from_unit], temp_units[to_unit])
    if from_t == to_t:
        return value
    if from_t == "celsius":
        return value * 9 / 5 + 32 if to_t == "fahrenheit" else value + 273.15
    if from_t == "fahrenheit":
        return (value - 32) * 5 / 9 if to_t == "celsius" else (value - 32) * 5 / 9 + 273.15
    return value - 273.15 if to_t == "celsius" else (value - 273.15) * 9 / 5 + 32


def _convert_length(
    value: float,
    from_unit: str,
    to_unit: str,
    length_units: dict[str, float],
) -> float:
    if from_unit not in length_units or to_unit not in length_units:
        raise MCPToolError(
            -32602,
            "Invalid length unit. Valid: m, km, cm, mi, yd, ft, in",
        )
    return value * length_units[from_unit] / length_units[to_unit]


def _convert_weight(
    value: float,
    from_unit: str,
    to_unit: str,
    weight_units: dict[str, float],
) -> float:
    if from_unit not in weight_units or to_unit not in weight_units:
        raise MCPToolError(
            -32602,
            "Invalid weight unit. Valid: kg, g, mg, lb, oz, t",
        )
    return value * weight_units[from_unit] / weight_units[to_unit]


def _convert_data(value: float, from_unit: str, to_unit: str, data_units: dict[str, int]) -> float:
    if from_unit not in data_units or to_unit not in data_units:
        raise MCPToolError(
            -32602,
            "Invalid data unit. Valid: b, kb, mb, gb, tb, pb",
        )
    return value * data_units[from_unit] / data_units[to_unit]
