"""SoAI - Plugin display-name resolution and caching [backend/plugins/manager/display_names.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "resolve_plugin_display_name",
    "resolve_plugin_display_names",
)

LOGGER_NAME = "SoAI.plugins.manager.display_names"
OPERATION = "plugin_manager.get_plugin_display_name"


async def resolve_plugin_display_name(self: PluginManagerRuntimeProtocol, plugin_name: str) -> str:
    logger = get_logger(LOGGER_NAME)
    self.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
    if not plugin_name:
        return "Unknown"
    if plugin_name in self.state.validation.display_name_cache:
        return self.state.validation.display_name_cache[plugin_name]
    async with self.state.validation.display_name_cache_lock:
        if plugin_name in self.state.validation.display_name_cache:
            return self.state.validation.display_name_cache[plugin_name]
        name, instance = (
            plugin_name,
            self.state.catalog.loaded_plugin_instances.get(plugin_name),
        )
        if instance:
            name_candidate = instance.NAME
            name = str(name_candidate or plugin_name).strip()
        else:
            try:
                db_info = await self.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
                if db_info:
                    db_name = db_info.get("name")
                    if isinstance(db_name, str) and db_name:
                        name = db_name
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Could not fetch display name for plugin from DB (non-critical).",
                    operation=OPERATION,
                    details={"plugin_name": plugin_name},
                    level="debug",
                )
        self.state.validation.display_name_cache[plugin_name] = name
        return name


async def resolve_plugin_display_names(
    self: PluginManagerRuntimeProtocol,
    plugin_names: Iterable[str],
) -> dict[str, str]:
    self.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
    ordered_unique = [name for name in dict.fromkeys(plugin_names) if name]
    if not ordered_unique:
        return {}
    display_name_tasks = [resolve_plugin_display_name(self, name) for name in ordered_unique]
    display_values = await asyncio.gather(*display_name_tasks, return_exceptions=False)
    return dict(zip(ordered_unique, display_values, strict=True))
