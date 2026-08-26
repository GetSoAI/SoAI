"""SoAI - MCP host-mode elicitation validation helpers [backend/mcp/host/elicitation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.mcp.jsonrpc_validation import (
    require_jsonrpc_dict,
    require_jsonrpc_nonempty_str,
    require_jsonrpc_nonempty_str_list,
)
from core.network.urls import require_absolute_http_url
from core.types.json import is_json_dict
from core.validation.integers import is_strict_int
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "get_elicitation_mode",
    "validate_elicitation_content",
    "validate_elicitation_field_value",
    "validate_elicitation_property_schema",
    "validate_elicitation_request_params",
    "validate_elicitation_schema",
)


def _invalid_params(message: str) -> MCPJSONRPCError:
    return MCPJSONRPCError(-32602, message)


def _read_const_choices(value: JSONValue, *, label: str) -> set[str]:
    if not isinstance(value, list) or not value:
        raise MCPJSONRPCError(-32602, f"{label} must be a non-empty list")
    choices: set[str] = set()
    for index, entry in enumerate(value):
        entry_schema = require_jsonrpc_dict(
            entry,
            build_error=_invalid_params,
            message=f"{label}[{index}] must be an object",
        )
        const_value = require_jsonrpc_nonempty_str(
            entry_schema.get("const"),
            build_error=_invalid_params,
            message=f"{label}[{index}].const must be a string",
        )
        title_value = entry_schema.get("title")
        if title_value is not None and (
            not isinstance(title_value, str) or not title_value.strip()
        ):
            raise MCPJSONRPCError(-32602, f"{label}[{index}].title must be a string")
        choices.add(const_value)
    if not choices:
        raise MCPJSONRPCError(-32602, f"{label} must include at least one choice")
    return choices


def _read_string_choices(schema: JSONDict, *, label: str) -> set[str] | None:
    if "enum" in schema:
        enum_value = schema["enum"]
        return set(
            require_jsonrpc_nonempty_str_list(
                enum_value,
                build_error=_invalid_params,
                message=f"{label} has invalid enum",
            ),
        )
    one_of = schema.get("oneOf")
    if one_of is not None:
        return _read_const_choices(one_of, label=f"{label}.oneOf")
    any_of = schema.get("anyOf")
    if any_of is not None:
        return _read_const_choices(any_of, label=f"{label}.anyOf")
    return None


def get_elicitation_mode(parameters: JSONDict) -> str:
    mode = parameters.get("mode")
    if mode is None:
        return "form"
    if not isinstance(mode, str):
        raise MCPJSONRPCError(-32602, "Invalid elicitation mode")
    mode = mode.strip()
    if mode not in ("form", "url"):
        raise MCPJSONRPCError(-32602, f"Unsupported elicitation mode: {mode}")
    return mode


def validate_elicitation_request_params(parameters: JSONDict) -> None:
    mode = get_elicitation_mode(parameters)
    require_jsonrpc_nonempty_str(
        parameters.get("message"),
        build_error=_invalid_params,
        message="Elicitation message is required",
    )
    if mode == "form":
        requested_schema = parameters.get("requestedSchema")
        requested_schema = require_jsonrpc_dict(
            requested_schema,
            build_error=_invalid_params,
            message="Elicitation form mode requires requestedSchema",
        )
        validate_elicitation_schema(requested_schema)
        return
    url = parameters.get("url")
    elicitation_id = parameters.get("elicitationId")
    normalized_url = require_jsonrpc_nonempty_str(
        url,
        build_error=_invalid_params,
        message="Elicitation url mode requires url",
    )
    require_jsonrpc_nonempty_str(
        elicitation_id,
        build_error=_invalid_params,
        message="Elicitation url mode requires elicitationId",
    )
    try:
        require_absolute_http_url(normalized_url)
    except ValidationError as exception:
        raise MCPJSONRPCError(
            -32602,
            "Elicitation url must be an absolute http(s) URL",
        ) from exception


def validate_elicitation_schema(schema: JSONDict) -> None:
    if schema.get("type") != "object":
        raise MCPJSONRPCError(-32602, "Elicitation requestedSchema must be an object schema")
    properties = require_jsonrpc_dict(
        schema.get("properties"),
        build_error=_invalid_params,
        message="Elicitation requestedSchema must define properties",
    )
    required = schema.get("required")
    if required is not None and (
        not isinstance(required, list)
        or not all(isinstance(field_name, str) and field_name for field_name in required)
    ):
        raise MCPJSONRPCError(
            -32602,
            "Elicitation requestedSchema.required must be a list of strings",
        )
    for key, value in properties.items():
        if not isinstance(key, str) or not key:
            raise MCPJSONRPCError(-32602, "Elicitation requestedSchema has invalid property name")
        if not is_json_dict(value):
            raise MCPJSONRPCError(-32602, f"Elicitation schema for '{key}' must be an object")
        validate_elicitation_property_schema(value, key)


def validate_elicitation_property_schema(property_schema: JSONDict, name: str) -> None:
    if "properties" in property_schema or property_schema.get("type") == "object":
        raise MCPJSONRPCError(
            -32602,
            f"Elicitation schema for '{name}' must be a primitive or enum",
        )
    schema_type = property_schema.get("type")
    _ = _read_string_choices(property_schema, label=f"Elicitation schema for '{name}'")
    if schema_type in (None, "string", "number", "integer", "boolean"):
        return
    if schema_type == "array":
        items = property_schema.get("items")
        if not is_json_dict(items):
            raise MCPJSONRPCError(
                -32602,
                f"Elicitation schema for '{name}' array must define items",
            )
        items_schema = items
        items_type = items_schema.get("type")
        if items_type not in (None, "string"):
            raise MCPJSONRPCError(
                -32602,
                f"Elicitation schema for '{name}' array items must be strings",
            )
        _ = _read_string_choices(items_schema, label=f"Elicitation schema for '{name}' array items")
        return
    raise MCPJSONRPCError(
        -32602,
        f"Elicitation schema for '{name}' has unsupported type: {schema_type}",
    )


def validate_elicitation_content(content: JSONDict, schema: JSONDict) -> None:
    properties_value = schema.get("properties")
    if not is_json_dict(properties_value):
        raise MCPJSONRPCError(-32602, "Elicitation requestedSchema must define properties")
    properties = properties_value
    required_value = schema.get("required", [])
    if not isinstance(required_value, list):
        raise MCPJSONRPCError(
            -32602,
            "Elicitation requestedSchema.required must be a list of strings",
        )
    required = required_value
    for key in required:
        if key not in content:
            raise MCPJSONRPCError(-32602, f"Missing required field: {key}")
    for key, value in content.items():
        if key not in properties:
            raise MCPJSONRPCError(-32602, f"Unexpected field: {key}")
        property_schema = properties[key]
        if not is_json_dict(property_schema):
            raise MCPJSONRPCError(-32602, f"Elicitation schema for '{key}' must be an object")
        validate_elicitation_field_value(key, value, property_schema)


def validate_elicitation_field_value(key: str, value: JSONValue, schema: JSONDict) -> None:
    schema_type = schema.get("type")
    choices = _read_string_choices(schema, label=f"Elicitation schema for field '{key}'")
    if schema_type in (None, "string"):
        if not isinstance(value, str):
            raise MCPJSONRPCError(-32602, f"Invalid value type for field: {key}")
        if choices is not None and value not in choices:
            raise MCPJSONRPCError(-32602, f"Invalid value for field: {key}")
        return
    if schema_type == "boolean":
        if not isinstance(value, bool):
            raise MCPJSONRPCError(-32602, f"Invalid value type for field: {key}")
        return
    if schema_type == "integer":
        if not is_strict_int(value):
            raise MCPJSONRPCError(-32602, f"Invalid value type for field: {key}")
        return
    if schema_type == "number":
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise MCPJSONRPCError(-32602, f"Invalid value type for field: {key}")
        return
    if schema_type == "array":
        if not isinstance(value, list):
            raise MCPJSONRPCError(-32602, f"Invalid value type for field: {key}")
        items_value = schema.get("items")
        item_choices: set[str] | None = None
        if is_json_dict(items_value):
            item_choices = _read_string_choices(
                items_value,
                label=f"Elicitation schema for field '{key}' array items",
            )
        for item in value:
            if not isinstance(item, str):
                raise MCPJSONRPCError(-32602, f"Invalid value type for field: {key}")
            if item_choices is not None and item not in item_choices:
                raise MCPJSONRPCError(-32602, f"Invalid value for field: {key}")
        return
    raise MCPJSONRPCError(-32602, f"Invalid value type for field: {key}")
