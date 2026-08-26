"""SoAI - Existing loaded-plugin outcome projection [backend/plugins/loader/loading_existing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.state.state_names import PLUGIN_STATE_NOT_DETECTED, resolve_plugin_runtime_state_name
from core.types.json import is_json_dict
from plugins.loader.loading_policy import PluginLoadOutcome
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = ("build_existing_plugin_load_outcome",)


async def build_existing_plugin_load_outcome(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> PluginLoadOutcome:
    instance = manager.state.catalog.loaded_plugin_instances.get(plugin_name)
    if instance is None:
        raise StateError(f"Plugin '{plugin_name}' is marked as loaded without an instance.")
    surface = manager.state.catalog.loaded_plugin_surfaces.get(plugin_name)
    surface_data = surface[0] if surface is not None else None
    if is_json_dict(surface_data):
        plugin_data = dict(surface_data)
    else:
        record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
        plugin_data = dict(record) if is_json_dict(record) else {}
    current_state = resolve_plugin_runtime_state_name(
        await manager.dependencies.infrastructure.state_aggregator.get_plugin_status(plugin_name)
    )
    resolved_state = current_state or PLUGIN_STATE_NOT_DETECTED
    welcome_message = (
        instance.WELCOME_MESSAGE if isinstance(instance.WELCOME_MESSAGE, str) else None
    )
    return PluginLoadOutcome(
        instance=instance,
        plugin_data=plugin_data,
        previous_state=resolved_state,
        initial_state=resolved_state,
        reason="Plugin was already loaded.",
        welcome_message=welcome_message,
    )
