"""SoAI - Plugin alias map hydration and lookup [backend/plugins/manager/alias_map.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.events.types_plugins import InstalledPluginsChangedEvent
from core.logging.trace import get_logger
from plugins.identity import normalize_plugin_lookup_key
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "hydrate_alias_map_from_database",
    "is_known_plugin",
    "normalize_plugin_name",
    "update_alias_map",
)

LOGGER_NAME = "SoAI.plugins.manager.alias_map"


async def hydrate_alias_map_from_database(
    self: PluginManagerRuntimeProtocol,
) -> None:
    hydrate_result = await self.state.lifecycle.alias_hydrator.hydrate(
        self.state.catalog.loaded_plugin_surfaces,
    )
    alias_map, known_plugins, display_cache = hydrate_result
    if alias_map is None or known_plugins is None:
        return
    async with self.state.locks.load_lock:
        self.state.catalog.alias_map = alias_map
        self.state.catalog.known_plugins = known_plugins
    if display_cache:
        async with self.state.validation.display_name_cache_lock:
            self.state.validation.display_name_cache.update(display_cache)


async def update_alias_map(manager: PluginManagerRuntimeProtocol) -> None:
    logger = get_logger(LOGGER_NAME)
    await hydrate_alias_map_from_database(manager)
    await manager.dependencies.infrastructure.event_bus.publish(
        InstalledPluginsChangedEvent(installed_plugin_names=manager.state.catalog.known_plugins),
    )
    logger.debug("Plugin alias map updated and change event published.")


def normalize_plugin_name(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str | float | None,
) -> str | None:
    self.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
    normalized_lookup_key = normalize_plugin_lookup_key(plugin_name)
    if normalized_lookup_key is None:
        return None
    normalized_name = self.state.catalog.alias_map.get(normalized_lookup_key)
    if isinstance(normalized_name, str) and normalized_name:
        return normalized_name
    if normalized_lookup_key in self.state.catalog.known_plugins:
        return normalized_lookup_key
    return None


def is_known_plugin(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str | float | None,
) -> bool:
    normalized_name = normalize_plugin_name(self, plugin_name)
    return bool(normalized_name and normalized_name in self.state.catalog.known_plugins)
