"""SoAI - Model manager plugin event handlers and discovery triggers [backend/models/manager/coordinator/plugin_event_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exceptions import StateError
from core.events.recent_event_tracker import RecentEventTracker
from core.events.types_base import Event
from core.events.types_models_model_events import ModelDatabaseChangeEvent
from core.events.types_plugins import (
    InstalledPluginsChangedEvent,
    PluginInstallationStateChangedEvent,
    PluginRuntimeStateChangedEvent,
    ProviderDiscoveryRequestedEvent,
)
from core.events.types_system import ConfigAppliedEvent
from core.logging.trace import get_logger
from core.models.discovery_trigger import publish_model_discovery_request
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_LOAD_ERROR,
    PLUGIN_STATE_PERSISTENT_READY,
    PLUGIN_STATE_STOPPED,
    PLUGIN_STATE_UPDATE_ERROR,
)
from core.validation.boolean_coercion import coerce_bool_flag
from models.manager.coordinator.dependencies import ModelManagerDependencies

__all__ = ("ModelManagerPluginEventHandlers",)

LOGGER_NAME = "SoAI.models.manager.plugin_event_handlers"
DISCOVERY_INSTALL_RECOVERY_TARGET_STATES = frozenset(
    (PLUGIN_STATE_STOPPED, PLUGIN_STATE_PERSISTENT_READY),
)
DISCOVERY_INSTALL_RECOVERY_SOURCE_STATES = frozenset(
    (PLUGIN_STATE_INSTALL_ERROR, PLUGIN_STATE_LOAD_ERROR, PLUGIN_STATE_UPDATE_ERROR),
)


class ModelManagerPluginEventHandlers:
    def __init__(self, *, deps: ModelManagerDependencies, shutdown_event: asyncio.Event) -> None:
        self._deps = deps
        self._shutdown_event = shutdown_event
        self._processed_authoritative_state_events = RecentEventTracker()

    async def seed_installed_plugin_names_snapshot(self) -> None:
        plugin_list = await self._deps.plugin_manager.list_plugins()
        if not isinstance(plugin_list, list):
            return
        installed_plugin_names: set[str] = set()
        for plugin_entry in plugin_list:
            if not isinstance(plugin_entry, dict):
                continue
            if not coerce_bool_flag(
                plugin_entry.get("installed"),
                logger=get_logger(LOGGER_NAME),
                operation="models.manager.coordinator.plugin_event_handlers.coerce_bool_flag",
                default=False,
                recover_message="Failed to parse boolean flag (non-critical).",
            ):
                continue
            plugin_name = plugin_entry.get("name")
            if not isinstance(plugin_name, str) or not plugin_name:
                continue
            installed_plugin_names.add(plugin_name)
        await self.apply_installed_plugin_names(installed_plugin_names)

    async def handle_provider_discovery_requested(self, event: Event) -> None:
        if not isinstance(event, ProviderDiscoveryRequestedEvent):
            return
        if self._shutdown_event.is_set():
            raise StateError("Provider discovery cannot be acknowledged during shutdown.")
        if await self._processed_authoritative_state_events.has_recent(event.event_id):
            return
        await self._deps.model_discovery_service.model_discover_all(
            plugins_to_scan=[event.plugin_name],
            wait_for_completion=True,
        )
        await self._deps.event_bus.publish(ModelDatabaseChangeEvent())
        await self._processed_authoritative_state_events.mark_processed(event.event_id)

    async def apply_installed_plugin_names(self, installed_plugin_names: set[str]) -> None:
        self._deps.set_installed_plugin_names(set(installed_plugin_names))
        if self._deps.model_registry is not None:
            await self._deps.model_registry.clear_plugin_info_cache()
        await self._deps.model_resolution_service.model_invalidate_resolution_cache()
        await self._deps.model_information_service.model_invalidate_list_caches()
        await self._purge_models_for_removed_plugins(set(installed_plugin_names))

    async def _invalidate_parameter_cache_for_plugin(self, plugin_name: str) -> None:
        models_by_plugin = await self._deps.database_models.get_all_models_by_plugin()
        for info in (models_by_plugin.get(plugin_name) or {}).values():
            if not isinstance(info, dict):
                continue
            universal_id = info.get("universal_id")
            if isinstance(universal_id, str) and universal_id:
                await self._deps.model_parameter_cache.invalidate(universal_id)

    async def _purge_models_for_removed_plugins(self, installed_plugin_names: set[str]) -> None:
        logger = get_logger(LOGGER_NAME)
        database_models = await self._deps.database_models.get_all_models_by_plugin()
        _ = installed_plugin_names
        removed_plugin_names = {
            plugin_name
            for plugin_name in database_models
            if not self._deps.plugin_manager.is_known_plugin(plugin_name)
        }
        if not removed_plugin_names:
            return
        display_names = await self._deps.plugin_manager.get_plugin_display_names(
            sorted(removed_plugin_names),
        )
        logger.info(
            "Plugins in DB no longer available: %s. Purging their models.",
            [display_names.get(name, name) for name in sorted(removed_plugin_names)],
        )
        await asyncio.gather(
            *[
                self._deps.model_actions_service.model_purge_for_plugin(plugin_name)
                for plugin_name in removed_plugin_names
            ],
            return_exceptions=False,
        )

    async def handle_installed_plugins_changed(self, event: Event) -> None:
        if not isinstance(event, InstalledPluginsChangedEvent):
            return
        if self._shutdown_event.is_set():
            return
        await self.apply_installed_plugin_names(set(event.installed_plugin_names))

    async def handle_plugin_enabled_status_change(self, event: Event) -> None:
        logger = get_logger(LOGGER_NAME)
        if not isinstance(event, PluginRuntimeStateChangedEvent):
            return
        if self._shutdown_event.is_set():
            return
        if await self._processed_authoritative_state_events.has_recent(event.event_id):
            return
        if (event.new_state == ORCH_STATE_DISABLED) != (
            event.previous_state == ORCH_STATE_DISABLED
        ):
            logger.info(
                "Plugin '%s' changed enabled status. Triggering model discovery.",
                event.plugin_name,
            )
            await publish_model_discovery_request(
                self._deps.event_bus,
                plugins_to_scan=[event.plugin_name],
            )
        await self._processed_authoritative_state_events.mark_processed(event.event_id)

    async def handle_plugin_install_state_change(self, event: Event) -> None:
        logger = get_logger(LOGGER_NAME)
        if not isinstance(event, PluginInstallationStateChangedEvent):
            return
        if self._shutdown_event.is_set():
            return
        if await self._processed_authoritative_state_events.has_recent(event.event_id):
            return
        if (
            self._deps.plugin_manager is not None
            and event.new_state in DISCOVERY_INSTALL_RECOVERY_TARGET_STATES
            and event.previous_state in DISCOVERY_INSTALL_RECOVERY_SOURCE_STATES
        ):
            logger.info(
                "Plugin '%s' backend installation recovered. Triggering model discovery.",
                event.plugin_name,
            )
            await publish_model_discovery_request(
                self._deps.event_bus,
                plugins_to_scan=[event.plugin_name],
            )
        await self._processed_authoritative_state_events.mark_processed(event.event_id)

    async def handle_plugin_config_applied(self, event: Event) -> None:
        logger = get_logger(LOGGER_NAME)
        if not isinstance(event, ConfigAppliedEvent):
            return
        if self._shutdown_event.is_set():
            return
        if not self._deps.plugin_manager.is_known_plugin(event.config_name):
            return
        if self._deps.model_registry is not None:
            await self._deps.model_registry.clear_plugin_info_cache()
        await self._invalidate_parameter_cache_for_plugin(event.config_name)
        await self._deps.model_resolution_service.model_invalidate_resolution_cache()
        await self._deps.model_information_service.model_invalidate_list_caches()
        logger.info(
            "Plugin '%s' configuration applied. Triggering model discovery.",
            event.config_name,
        )
        await publish_model_discovery_request(
            self._deps.event_bus,
            plugins_to_scan=[event.config_name],
        )
