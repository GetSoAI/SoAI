"""SoAI - Plugin instance lifecycle and caching [backend/plugins/manager/instances.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.protocols_instance import PluginInstanceProtocol
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "clear_loaded_plugin_state",
    "get_plugin_instance",
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
    *,
    expected_instance: PluginInstanceProtocol | None = None,
) -> None:
    async with manager.state.locks.load_lock:
        current_instance = manager.state.catalog.loaded_plugin_instances.get(plugin_name)
        readers = manager.state.catalog.model_catalog_reads.get(id(current_instance))
        if (
            expected_instance is not None
            and current_instance is expected_instance
            and readers is not None
            and readers.users > 0
        ):
            return
        owns_catalog = expected_instance is None or current_instance is expected_instance
        loaded_surface = (
            manager.state.catalog.loaded_plugin_surfaces.pop(plugin_name, None)
            if owns_catalog
            else None
        )
        loaded_instance = (
            manager.state.catalog.loaded_plugin_instances.pop(plugin_name, None)
            if owns_catalog
            else None
        )
    worker_stopped = False
    try:
        if expected_instance is None:
            await manager.worker_controller.stop_plugin(plugin_name)
        else:
            await manager.worker_controller.stop_plugin(
                plugin_name, expected_instance=expected_instance
            )
        worker_stopped = True
        async with manager.state.locks.load_lock:
            manager.state.catalog.model_catalog_reads.pop(
                id(expected_instance if expected_instance is not None else current_instance), None
            )
    finally:
        if not worker_stopped:
            async with manager.state.locks.load_lock:
                if loaded_surface is not None and (
                    plugin_name not in manager.state.catalog.loaded_plugin_surfaces
                ):
                    manager.state.catalog.loaded_plugin_surfaces[plugin_name] = loaded_surface
                if loaded_instance is not None and (
                    plugin_name not in manager.state.catalog.loaded_plugin_instances
                ):
                    manager.state.catalog.loaded_plugin_instances[plugin_name] = loaded_instance
    cleared = owns_catalog or current_instance is None
    if expected_instance is not None and cleared:
        async with manager.state.locks.load_lock:
            if plugin_name not in manager.state.catalog.loaded_plugin_instances:
                await manager.dependencies.databases.plugins.update_plugin_runtime_loaded(
                    plugin_name, False
                )
