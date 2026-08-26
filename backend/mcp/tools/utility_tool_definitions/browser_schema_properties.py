"""SoAI - Browser MCP input schema property builders [backend/mcp/tools/utility_tool_definitions/browser_schema_properties.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "non_empty_string_array_schema",
    "non_empty_string_schema",
    "nullable_boolean_schema",
    "nullable_enum_schema",
    "nullable_integer_schema",
    "nullable_non_empty_string_array_schema",
    "nullable_non_empty_string_schema",
    "nullable_number_schema",
)


def non_empty_string_schema(*, description: str | None = None) -> JSONDict:
    schema: JSONDict = {"type": "string", "minLength": 1}
    if description is not None:
        schema["description"] = description
    return schema


def nullable_non_empty_string_schema(*, description: str | None = None) -> JSONDict:
    schema: JSONDict = {"type": ["string", "null"], "minLength": 1}
    if description is not None:
        schema["description"] = description
    return schema


def nullable_enum_schema(
    values: tuple[str, ...],
    *,
    description: str | None = None,
) -> JSONDict:
    schema: JSONDict = {"type": ["string", "null"], "enum": [*values, None]}
    if description is not None:
        schema["description"] = description
    return schema


def nullable_boolean_schema(*, description: str | None = None) -> JSONDict:
    schema: JSONDict = {"type": ["boolean", "null"]}
    if description is not None:
        schema["description"] = description
    return schema


def nullable_integer_schema(
    *,
    minimum: int | None = None,
    maximum: int | None = None,
    description: str | None = None,
) -> JSONDict:
    schema: JSONDict = {"type": ["integer", "null"]}
    if minimum is not None:
        schema["minimum"] = int(minimum)
    if maximum is not None:
        schema["maximum"] = int(maximum)
    if description is not None:
        schema["description"] = description
    return schema


def nullable_number_schema(
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    description: str | None = None,
) -> JSONDict:
    schema: JSONDict = {"type": ["number", "null"]}
    if minimum is not None:
        schema["minimum"] = float(minimum)
    if maximum is not None:
        schema["maximum"] = float(maximum)
    if description is not None:
        schema["description"] = description
    return schema


def non_empty_string_array_schema(
    *,
    description: str | None = None,
    max_items: int | None = None,
) -> JSONDict:
    schema: JSONDict = {
        "type": "array",
        "items": non_empty_string_schema(),
        "minItems": 1,
    }
    if max_items is not None:
        schema["maxItems"] = int(max_items)
    if description is not None:
        schema["description"] = description
    return schema


def nullable_non_empty_string_array_schema(
    *,
    description: str | None = None,
    max_items: int | None = None,
) -> JSONDict:
    schema = non_empty_string_array_schema(max_items=max_items)
    schema["type"] = ["array", "null"]
    if description is not None:
        schema["description"] = description
    return schema
