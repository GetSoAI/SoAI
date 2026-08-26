"""SoAI - Parameter reload matching for task tracking [backend/orchestrator/lifecycle/task_tracking/param_matching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.reload_policy import filter_reload_parameters
from core.errors.exceptions import StateError
from core.models.protocols import ParameterManagerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "check_reload_params_match",
    "get_reload_parameters",
)


async def get_reload_parameters(
    plugin_name: str,
    all_params: JSONDict | None,
    param_manager: ParameterManagerProtocol,
) -> dict[str, JSONValue]:
    if not all_params:
        return {}
    schema = await param_manager.get_all_parameters_for_plugin(plugin_name)
    if not isinstance(schema, dict):
        raise StateError(
            "Parameter schema must be a dict.",
            operation="orchestrator.task_tracking.get_reload_parameters",
            details={"plugin_name": plugin_name, "schema_type": type(schema).__name__},
        )
    parameters_payload: JSONDict = dict(all_params)
    return filter_reload_parameters(schema, parameters_payload)


async def check_reload_params_match(
    plugin_name: str,
    loaded_params: JSONDict | None,
    request_params: JSONDict,
    param_manager: ParameterManagerProtocol,
) -> bool:
    loaded_reload = await get_reload_parameters(plugin_name, loaded_params, param_manager)
    request_reload = await get_reload_parameters(plugin_name, request_params, param_manager)
    return loaded_reload == request_reload
