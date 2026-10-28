"""SoAI - Model parameter schema access helpers [backend/models/parameters/schema_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.errors.exceptions import ValidationError
from core.models.parameter_errors import build_model_parameter_schema_unavailable_error
from core.models.persisted_parameter_values import resolve_effective_parameter_values
from core.models.protocols import ParameterManagerProtocol
from core.plugins.protocols_lifecycle import PluginLifecycleProtocol
from core.types.json import JSONDict, is_json_dict

__all__ = (
    "get_effective_parameters",
    "get_validated_parameter_schema",
    "require_locked_parameter_definitions",
    "require_parameter_schema_snapshot",
)


async def get_effective_parameters(
    param_manager: ParameterManagerProtocol,
    plugin_name: str,
    custom_parameters: JSONDict,
) -> JSONDict:
    schema = await param_manager.get_all_parameters_for_plugin(plugin_name)
    if not isinstance(schema, dict):
        raise ValidationError(f"Parameter schema for plugin '{plugin_name}' must be a mapping.")
    return resolve_effective_parameter_values(schema, custom_parameters)


async def require_parameter_schema_snapshot(
    *,
    param_manager: ParameterManagerProtocol,
    plugin_lifecycle: PluginLifecycleProtocol,
    plugin_name: str,
) -> tuple[JSONDict, JSONDict]:
    snapshot = await param_manager.get_parameter_schema_snapshot(plugin_name)
    if snapshot is None:
        raise build_model_parameter_schema_unavailable_error(
            plugin_name,
            operation_in_progress=plugin_lifecycle.is_plugin_locked(plugin_name),
        )
    return snapshot


async def require_locked_parameter_definitions(
    *,
    param_manager: ParameterManagerProtocol,
    plugin_name: str,
) -> JSONDict:
    snapshot = await param_manager.get_parameter_schema_snapshot(plugin_name)
    if snapshot is None:
        raise build_model_parameter_schema_unavailable_error(
            plugin_name, operation_in_progress=False
        )
    return _select_parameter_definitions(snapshot[0])


async def get_validated_parameter_schema(
    *,
    universal_id: str,
    model_validate_and_get_context: Callable[[str], Awaitable[tuple[JSONDict, str]]],
    param_manager: ParameterManagerProtocol,
    plugin_lifecycle: PluginLifecycleProtocol,
) -> tuple[str, JSONDict]:
    _, plugin_name = await model_validate_and_get_context(universal_id)
    raw_schema, _categories = await require_parameter_schema_snapshot(
        param_manager=param_manager,
        plugin_lifecycle=plugin_lifecycle,
        plugin_name=plugin_name,
    )
    return (plugin_name, _select_parameter_definitions(raw_schema))


def _select_parameter_definitions(raw_schema: JSONDict) -> JSONDict:
    schema: JSONDict = {}
    for key, definition in raw_schema.items():
        if isinstance(key, str) and is_json_dict(definition):
            schema[key] = definition
    return schema
