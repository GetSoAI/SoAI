"""SoAI - Model parameter schema access helpers [backend/models/parameters/schema_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.errors.exceptions import ValidationError
from core.models.protocols import ParameterManagerProtocol
from core.types.json import JSONDict

__all__ = (
    "get_default_parameters",
    "get_validated_parameter_schema",
)


async def get_default_parameters(
    param_manager: ParameterManagerProtocol,
    plugin_name: str,
) -> JSONDict:
    schema = await param_manager.get_all_parameters_for_plugin(plugin_name)
    defaults: JSONDict = {}
    if not isinstance(schema, dict):
        return defaults
    for name, definition in schema.items():
        if not isinstance(definition, dict):
            continue
        if definition.get("has_default", "default" in definition):
            defaults[name] = definition.get("default")
    return defaults


async def get_validated_parameter_schema(
    *,
    universal_id: str,
    model_validate_and_get_context: Callable[[str], Awaitable[tuple[JSONDict, str]]],
    param_manager: ParameterManagerProtocol,
) -> tuple[str, JSONDict]:
    _, plugin_name = await model_validate_and_get_context(universal_id)
    raw_schema = await param_manager.get_all_parameters_for_plugin(plugin_name)
    if not isinstance(raw_schema, dict):
        raise ValidationError(f"Parameter schema for plugin '{plugin_name}' must be a mapping.")
    schema: JSONDict = {}
    for key, definition in raw_schema.items():
        if isinstance(key, str) and isinstance(definition, dict):
            schema[key] = definition
    return (plugin_name, schema)
