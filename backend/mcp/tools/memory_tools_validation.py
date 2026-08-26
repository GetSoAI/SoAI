"""SoAI - MCP memory tool input validation helpers [backend/mcp/tools/memory_tools_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.argument_numbers import parse_required_json_int_value
from core.mcp.argument_validation import (
    require_json_dict_list_argument,
    require_no_unknown_keys,
    require_non_empty_string_value,
    require_unique_non_empty_string_list_argument,
)
from mcp.tools.error import MCPToolError, build_invalid_params_error

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "parse_entities",
    "parse_limit",
    "parse_observations",
    "parse_relations",
    "require_dict_list",
    "require_non_empty_str",
    "require_str_list",
)


def require_non_empty_str(value: JSONValue, *, label: str) -> str:
    return require_non_empty_string_value(
        value,
        build_error=build_invalid_params_error,
        type_message=f"{label} must be a non-empty string.",
        empty_message=f"{label} must be a non-empty string.",
    )


def parse_limit(value: JSONValue, *, provided: bool) -> int:
    if not provided:
        return 10
    return parse_required_json_int_value(
        value,
        build_error=build_invalid_params_error,
        integer_message="limit must be an integer between 1 and 50.",
        range_message="limit must be an integer between 1 and 50.",
        min_value=1,
        max_value=50,
    )


def require_dict_list(arguments: JSONDict, key: str) -> list[JSONDict]:
    return require_json_dict_list_argument(
        arguments,
        key,
        build_error=build_invalid_params_error,
    )


def require_str_list(arguments: JSONDict, key: str) -> list[str]:
    return require_unique_non_empty_string_list_argument(
        arguments,
        key,
        build_error=build_invalid_params_error,
    )


def _require_allowed_item_keys(item: JSONDict, allowed_keys: set[str], label: str) -> None:
    require_no_unknown_keys(
        item,
        allowed_keys,
        build_error=build_invalid_params_error,
        message=lambda invalid_keys: f"Unsupported parameter in {label}: {invalid_keys[0]}",
    )


def parse_entities(raw_entities: list[JSONDict]) -> list[JSONDict]:
    parsed: list[JSONDict] = []
    seen_names: set[str] = set()
    for index, item in enumerate(raw_entities):
        _require_allowed_item_keys(item, {"name", "entity_type"}, f"entities[{index}]")
        name = require_non_empty_str(item.get("name"), label=f"entities[{index}].name")
        entity_type = require_non_empty_str(
            item.get("entity_type"),
            label=f"entities[{index}].entity_type",
        )
        if name in seen_names:
            raise MCPToolError(-32602, f"entities[{index}].name duplicates '{name}'.")
        seen_names.add(name)
        parsed.append({"name": name, "entity_type": entity_type})
    return parsed


def parse_observations(raw_observations: list[JSONDict]) -> list[JSONDict]:
    parsed: list[JSONDict] = []
    for index, item in enumerate(raw_observations):
        _require_allowed_item_keys(
            item,
            {"entity_name", "content", "source"},
            f"observations[{index}]",
        )
        entity_name = require_non_empty_str(
            item.get("entity_name"),
            label=f"observations[{index}].entity_name",
        )
        content = require_non_empty_str(item.get("content"), label=f"observations[{index}].content")
        source_value = item["source"] if "source" in item else None
        source: str | None = None
        if "source" in item:
            source = require_non_empty_str(source_value, label=f"observations[{index}].source")
        parsed.append({"entity_name": entity_name, "content": content, "source": source})
    return parsed


def parse_relations(raw_relations: list[JSONDict]) -> list[JSONDict]:
    parsed: list[JSONDict] = []
    seen_relations: set[tuple[str, str, str]] = set()
    for index, item in enumerate(raw_relations):
        _require_allowed_item_keys(
            item,
            {"from_entity", "to_entity", "relation_type"},
            f"relations[{index}]",
        )
        from_entity = require_non_empty_str(
            item.get("from_entity"),
            label=f"relations[{index}].from_entity",
        )
        to_entity = require_non_empty_str(
            item.get("to_entity"),
            label=f"relations[{index}].to_entity",
        )
        relation_type = require_non_empty_str(
            item.get("relation_type"),
            label=f"relations[{index}].relation_type",
        )
        relation_key = (from_entity, to_entity, relation_type)
        if relation_key in seen_relations:
            relation_text = f"({from_entity}, {to_entity}, {relation_type})"
            raise MCPToolError(
                -32602,
                f"relations[{index}] duplicates relation {relation_text}.",
            )
        seen_relations.add(relation_key)
        parsed.append(
            {
                "from_entity": from_entity,
                "to_entity": to_entity,
                "relation_type": relation_type,
            },
        )
    return parsed
