"""SoAI - Schema-driven plugin CLI argument rendering [backend/plugin_sdk/contracts/schema_cli_arguments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.models.parameter_schema_contract import (
    validate_parameter_definitions,
    validate_parameter_value,
)
from core.serialization.json import serialize_json_compact_stable
from core.types.json import is_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_schema_cli_arguments",)


def _render_scalar(value: JSONValue) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict | list):
        return serialize_json_compact_stable(value)
    return str(value)


def _require_cli_name(parameter_name: str, definition: JSONDict) -> str:
    cli_name = definition.get("cli_name")
    if not isinstance(cli_name, str) or not cli_name.strip():
        raise ValidationError(f"Parameter '{parameter_name}' requires a non-empty cli_name.")
    return cli_name.strip()


def _render_dual_flag(parameter_name: str, definition: JSONDict, value: JSONValue) -> str | None:
    dual_cli_names = definition.get("dual_cli_names")
    if not is_json_dict(dual_cli_names):
        raise ValidationError(f"Parameter '{parameter_name}' has invalid dual_cli_names.")
    if not isinstance(value, str):
        raise ValidationError(f"Dual flag parameter '{parameter_name}' must be a string.")
    normalized = value.strip().lower()
    if normalized in {"default", "auto"}:
        return None
    cli_name = dual_cli_names.get(normalized)
    if not isinstance(cli_name, str) or not cli_name.strip():
        raise ValidationError(f"Dual flag parameter '{parameter_name}' has no matching flag.")
    return cli_name.strip()


def _render_array(
    parameter_name: str,
    definition: JSONDict,
    cli_name: str,
    value: list[JSONValue],
) -> list[str]:
    if not value:
        return []
    rendered_items = [_render_scalar(item).strip() for item in value]
    if any(not item for item in rendered_items):
        raise ValidationError(f"Array parameter '{parameter_name}' contains an empty value.")
    rendering = definition.get("rendering", "single")
    if rendering == "comma_separated":
        return [cli_name, ",".join(rendered_items)]
    if rendering == "repeat":
        arguments: list[str] = []
        for rendered_item in rendered_items:
            arguments.extend((cli_name, rendered_item))
        return arguments
    if rendering != "single":
        raise ValidationError(f"Array parameter '{parameter_name}' has invalid rendering.")
    return [cli_name, *rendered_items]


def build_schema_cli_arguments(
    parameter_definitions: JSONDict,
    parameter_values: JSONDict,
    *,
    group: str,
) -> list[str]:
    if not group.strip():
        raise ValidationError("Schema CLI argument group must be non-empty.")
    validate_parameter_definitions(parameter_definitions)
    arguments: list[str] = []
    for parameter_name, definition_value in parameter_definitions.items():
        if not is_json_dict(definition_value) or definition_value.get("group") != group:
            continue
        if parameter_name not in parameter_values:
            continue
        value = parameter_values.get(parameter_name)
        if value is None:
            continue
        validate_parameter_value(
            definition=definition_value,
            value=value,
            label=f"Parameter '{parameter_name}'",
        )
        if definition_value.get("rendering") == "dual_flag" or "dual_cli_names" in definition_value:
            dual_flag = _render_dual_flag(parameter_name, definition_value, value)
            if dual_flag is not None:
                arguments.append(dual_flag)
            continue
        cli_name = _require_cli_name(parameter_name, definition_value)
        if (
            definition_value.get("is_boolean_flag") is True
            or definition_value.get("rendering") == "flag"
        ):
            if not isinstance(value, bool):
                raise ValidationError(f"Boolean flag parameter '{parameter_name}' must be boolean.")
            if value:
                arguments.append(cli_name)
            continue
        if isinstance(value, list):
            arguments.extend(_render_array(parameter_name, definition_value, cli_name, value))
            continue
        rendered_value = (
            _render_scalar(value).strip() if isinstance(value, str) else _render_scalar(value)
        )
        if not rendered_value:
            raise ValidationError(f"Parameter '{parameter_name}' must not be empty.")
        if rendered_value.lower() == "auto" and definition_value.get("default") == "auto":
            continue
        arguments.extend((cli_name, rendered_value))
    return arguments
