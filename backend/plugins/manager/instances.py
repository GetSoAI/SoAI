"""SoAI - Plugin instance lifecycle and caching [backend/plugins/manager/instances.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ProcessError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.plugins.protocols_instance import PluginInstanceProtocol
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "clear_loaded_plugin_state",
    "get_plugin_instance",
)

PLUGIN_STOP_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    ProcessError,
)


async def get_plugin_instance(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> PluginInstanceProtocol | None:
    self.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
    async with self.state.locks.load_lock:
        return self.state.catalog.loaded_plugin_instances.get(plugin_name)


async def clear_loaded_plugin_state(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> None:
    async with manager.state.locks.load_lock:
        loaded_surface = manager.state.catalog.loaded_plugin_surfaces.pop(plugin_name, None)
        loaded_instance = manager.state.catalog.loaded_plugin_instances.pop(plugin_name, None)
    try:
        await manager.worker_controller.stop_plugin(plugin_name)
    except PLUGIN_STOP_EXCEPTIONS:
        async with manager.state.locks.load_lock:
            if loaded_surface is not None and (
                plugin_name not in manager.state.catalog.loaded_plugin_surfaces
            ):
                manager.state.catalog.loaded_plugin_surfaces[plugin_name] = loaded_surface
            if loaded_instance is not None and (
                plugin_name not in manager.state.catalog.loaded_plugin_instances
            ):
                manager.state.catalog.loaded_plugin_instances[plugin_name] = loaded_instance
        raise
