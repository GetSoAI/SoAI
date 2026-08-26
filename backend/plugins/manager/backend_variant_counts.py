"""SoAI - Plugin backend variant count refresh and listing support [backend/plugins/manager/backend_variant_counts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.events.types_plugins import InstalledPluginsChangedEvent
from core.plugins.backend_variants import count_available_backend_variant_options
from core.state.state_names import PLUGIN_STATE_BACKEND_NOT_INSTALLED
from core.types.json import JSONDict
from core.validation.boolean_coercion import coerce_bool_with_recovery
from core.validation.coercion import coerce_non_negative_int_from_numberish
from plugins.manager.backend_variant_option_loading import load_backend_variant_options
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "merge_persisted_backend_variant_counts",
    "persist_backend_variant_count",
    "persist_backend_variant_count_without_event",
    "refresh_backend_variant_count",
)

OPERATION_BACKEND_VARIANT_COUNT_SUPPORT = "plugins.manager.backend_variant_counts.support"


def _supports_backend_installation(
    manager: PluginManagerRuntimeProtocol,
    plugin_data: JSONDict,
) -> bool:
    return coerce_bool_with_recovery(
        plugin_data,
        "supports_backend_installation",
        logger=manager.logger,
        operation=OPERATION_BACKEND_VARIANT_COUNT_SUPPORT,
        default=False,
    )


def _needs_backend_variant_count(
    manager: PluginManagerRuntimeProtocol,
    plugin_data: JSONDict,
    effective_state: str,
) -> bool:
    plugin_name = plugin_data.get("plugin_name")
    return (
        isinstance(plugin_name, str)
        and plugin_name != ""
        and _supports_backend_installation(manager, plugin_data)
        and effective_state == PLUGIN_STATE_BACKEND_NOT_INSTALLED
    )


def _resolve_persisted_count(plugin_data: JSONDict) -> int:
    count_value = plugin_data.get("backend_variant_available_count")
    if count_value is None:
        return 1
    return coerce_non_negative_int_from_numberish(count_value)


def merge_persisted_backend_variant_counts(
    manager: PluginManagerRuntimeProtocol,
    database_plugins: list[JSONDict],
    stats: dict[str, dict[str, int]],
    backend_installation_overrides: dict[str, str],
) -> None:
    for plugin_data in database_plugins:
        plugin_name_value = plugin_data.get("plugin_name")
        if not isinstance(plugin_name_value, str) or not plugin_name_value:
            continue
        effective_state = backend_installation_overrides.get(
            plugin_name_value,
            str(plugin_data.get("state") or ""),
        )
        if not _needs_backend_variant_count(manager, plugin_data, effective_state):
            continue
        if plugin_name_value not in stats:
            stats[plugin_name_value] = {"model_count": 0, "provider_count": 0}
        stats[plugin_name_value]["backend_variant_available_count"] = _resolve_persisted_count(
            plugin_data,
        )


async def refresh_backend_variant_count(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> bool:
    async with manager.state.catalog.backend_variant_count_locks.lock(plugin_name):
        plugin_record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
        if plugin_record is None:
            return False
        state_value = plugin_record.get("state")
        state = state_value if isinstance(state_value, str) else ""
        if not _needs_backend_variant_count(manager, plugin_record, state):
            return False
        options = await load_backend_variant_options(manager, plugin_name)
        return await persist_backend_variant_count(
            manager,
            plugin_name,
            state,
            options,
        )


async def persist_backend_variant_count(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    expected_state: str,
    options: list[JSONDict],
) -> bool:
    changed = await persist_backend_variant_count_without_event(
        manager,
        plugin_name,
        expected_state,
        options,
    )
    if changed:
        await manager.dependencies.infrastructure.event_bus.publish(
            InstalledPluginsChangedEvent(
                installed_plugin_names=manager.state.catalog.known_plugins
            ),
        )
    return changed


async def persist_backend_variant_count_without_event(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    expected_state: str,
    options: list[JSONDict],
) -> bool:
    if expected_state != PLUGIN_STATE_BACKEND_NOT_INSTALLED:
        return False
    available_count = count_available_backend_variant_options(options)
    return await manager.dependencies.databases.plugins.update_backend_variant_available_count(
        plugin_name,
        expected_state,
        available_count,
    )
