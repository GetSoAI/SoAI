"""SoAI - Plugin post-load side effects and announcement [backend/plugins/loader/loading_side_effects.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from plugins.fs_permissions import ensure_single_path_permissions
from plugins.identity import normalize_plugin_display_name
from plugins.manager.alias_map import update_alias_map
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.types.json import JSONDict

__all__ = ("prepare_loaded_plugin_side_effects",)


async def prepare_loaded_plugin_side_effects(
    manager: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    plugin_data: JSONDict,
    final_instance: PluginInstanceProtocol,
) -> None:
    try:
        install_path = final_instance.install_path
    except AttributeError:
        install_path = None
    if not isinstance(install_path, str) or not install_path:
        raise StateError(f"Plugin '{plugin_name}' did not provide a valid install_path.")
    await ensure_single_path_permissions(install_path)
    cached_display_name = normalize_plugin_display_name(plugin_name, plugin_data)
    async with manager.state.validation.display_name_cache_lock:
        manager.state.validation.display_name_cache[plugin_name] = cached_display_name
    if manager.dependencies.infrastructure.state_aggregator is not None:
        await manager.dependencies.infrastructure.state_aggregator.clear_purged_status(plugin_name)
    await update_alias_map(manager)
