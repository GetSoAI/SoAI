"""SoAI - Plugin backend variant manager operations [backend/plugins/manager/backend_variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.backend_variant_status import read_installed_backend_variant_id
from core.plugins.backend_variants import (
    AUTO_BACKEND_VARIANT_ID,
    count_available_backend_variant_options,
    is_backend_variant_available,
    require_backend_variant_id,
    require_known_backend_variant_id,
)
from core.types.json import JSONDict, JSONValue
from plugins.manager.backend_variant_counts import persist_backend_variant_count
from plugins.manager.backend_variant_option_loading import load_backend_variant_options
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "get_backend_variants",
    "save_backend_variant_selection",
    "snapshot_backend_variant_selection",
)


async def snapshot_backend_variant_selection(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    requested_variant_id: JSONValue = None,
    *,
    has_requested_variant_id: bool = False,
) -> str:
    if has_requested_variant_id:
        variant_id = require_backend_variant_id(requested_variant_id)
    else:
        raw_variant_id = await manager.dependencies.databases.plugins.get_backend_variant_id(
            plugin_name,
        )
        variant_id = require_backend_variant_id(raw_variant_id or AUTO_BACKEND_VARIANT_ID)
    options = await load_backend_variant_options(manager, plugin_name)
    if not has_requested_variant_id and not is_backend_variant_available(variant_id, options):
        return AUTO_BACKEND_VARIANT_ID
    return require_known_backend_variant_id(variant_id, options)


async def resolve_installed_backend_variant_id(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> str | None:
    instance = await manager.get_plugin_instance(plugin_name)
    if instance is None:
        return None
    return read_installed_backend_variant_id(await instance.get_status())


async def get_backend_variants(manager: PluginManagerRuntimeProtocol, plugin_name: str) -> JSONDict:
    selected = await manager.dependencies.databases.plugins.get_backend_variant_id(plugin_name)
    selected_variant_id = require_backend_variant_id(selected or AUTO_BACKEND_VARIANT_ID)
    plugin_record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    options = await load_backend_variant_options(manager, plugin_name)
    if not is_backend_variant_available(selected_variant_id, options):
        selected_variant_id = AUTO_BACKEND_VARIANT_ID
    result: JSONDict = {
        "selected_variant_id": selected_variant_id,
        "installed_variant_id": await resolve_installed_backend_variant_id(manager, plugin_name),
        "options": options,
        "available_count": count_available_backend_variant_options(options),
    }
    state_value = plugin_record.get("state") if plugin_record is not None else None
    if isinstance(state_value, str):
        await persist_backend_variant_count(manager, plugin_name, state_value, options)
    return result


async def save_backend_variant_selection(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    variant_id: JSONValue,
) -> JSONDict:
    plugin_record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    options = await load_backend_variant_options(manager, plugin_name)
    selected_variant_id = require_known_backend_variant_id(variant_id, options)
    await manager.dependencies.databases.plugins.set_backend_variant_id(
        plugin_name,
        selected_variant_id,
    )
    result: JSONDict = {
        "selected_variant_id": selected_variant_id,
        "installed_variant_id": await resolve_installed_backend_variant_id(manager, plugin_name),
        "options": options,
        "available_count": count_available_backend_variant_options(options),
    }
    state_value = plugin_record.get("state") if plugin_record is not None else None
    if isinstance(state_value, str):
        await persist_backend_variant_count(manager, plugin_name, state_value, options)
    return result
