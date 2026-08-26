"""SoAI - MCP utility handler and definition validation [backend/mcp/tools/handler_definition_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ConfigurationError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_allowed_keys_by_tool_name",
    "validate_utility_tool_handler_definitions",
)


def build_allowed_keys_by_tool_name(definitions: dict[str, JSONDict]) -> dict[str, frozenset[str]]:
    allowed_keys_by_tool_name: dict[str, frozenset[str]] = {}
    for tool_name, definition in definitions.items():
        input_schema = definition.get("input_schema")
        if not isinstance(input_schema, dict):
            continue
        properties = input_schema.get("properties")
        if not isinstance(properties, dict):
            continue
        additional_properties = input_schema.get("additionalProperties")
        if additional_properties is not False:
            continue
        allowed_keys_by_tool_name[tool_name] = frozenset(str(key) for key in properties)
    return allowed_keys_by_tool_name


def validate_utility_tool_handler_definitions(
    *,
    definitions: dict[str, JSONDict],
    handlers: dict[str, Callable[[JSONDict], Awaitable[JSONValue]]],
) -> None:
    definition_names = set(definitions.keys())
    handler_names = set(handlers.keys())
    missing_definitions = sorted(handler_names - definition_names)
    missing_handlers = sorted(definition_names - handler_names)
    if missing_definitions or missing_handlers:
        details: list[str] = []
        if missing_definitions:
            details.append(f"handlers_without_definitions={','.join(missing_definitions)}")
        if missing_handlers:
            details.append(f"definitions_without_handlers={','.join(missing_handlers)}")
        raise ConfigurationError(
            f"MCP utility tool registry is inconsistent ({'; '.join(details)}).",
        )
