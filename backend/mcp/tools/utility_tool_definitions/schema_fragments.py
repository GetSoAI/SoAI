"""SoAI - MCP utility tool schema fragments [backend/mcp/tools/utility_tool_definitions/schema_fragments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_object_input_schema", "build_required_query_property")


def build_object_input_schema(
    *,
    properties: JSONDict,
    required: list[str],
) -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def build_required_query_property(
    *,
    description: str,
    max_length: int | None = None,
) -> JSONDict:
    property_schema: JSONDict = {
        "type": "string",
        "minLength": 1,
        "description": description,
    }
    if max_length is not None:
        property_schema["maxLength"] = max_length
    return property_schema
