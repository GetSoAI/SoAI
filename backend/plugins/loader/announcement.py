"""SoAI - Plugin load announcement helpers [backend/plugins/loader/announcement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ServiceUnavailableError
from core.events.types_plugins import PluginLoadedEvent
from core.logging.trace import get_logger
from core.state.state_names import resolve_plugin_runtime_state_name
from plugins.identity import normalize_plugin_display_name
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.publication_wait import wait_for_plugin_state_publication
from plugins.state.transition_logging import log_skipped_same_state_transition

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("announce_loaded_plugin",)

LOGGER_NAME = "SoAI.plugins.loader.announcement"


async def announce_loaded_plugin(
    manager: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    welcome_message: str | None,
    plugin_data: JSONDict,
    previous_state: str,
    initial_state: str,
    reason: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    previous_state_name = resolve_plugin_runtime_state_name(previous_state)
    initial_state_name = resolve_plugin_runtime_state_name(initial_state)
    if previous_state_name is None or initial_state_name is None:
        logger.warning(
            "Skipping plugin state announcement for '%s' due to invalid state values: %s -> %s",
            plugin_name,
            previous_state,
            initial_state,
        )
        return
    if previous_state != initial_state:
        try:
            receipt = await manager.transition_plugin_manager_state(
                plugin_name,
                initial_state_name,
                reason,
            )
        except ServiceUnavailableError as exception:
            logger.error(
                "Failed to announce plugin '%s' state transition: %s",
                plugin_name,
                exception.message,
                extra={
                    "plugin_name": plugin_name,
                    "previous_state": previous_state_name,
                    "new_state": initial_state_name,
                    "details": exception.details,
                    "operation": exception.operation,
                },
            )
            raise
        await wait_for_plugin_state_publication(receipt)
    else:
        log_skipped_same_state_transition(logger, plugin_name, previous_state, initial_state)
    await manager.dependencies.infrastructure.event_bus.publish(
        PluginLoadedEvent(plugin_name=plugin_name),
    )
    db_record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    if (
        isinstance(welcome_message, str)
        and welcome_message.strip()
        and db_record
        and (not db_record.get("welcome_message_logged"))
    ):
        logger.info("[%s] Welcome: %s", plugin_name, welcome_message.strip())
        await manager.dependencies.databases.plugins.mark_welcome_message_logged(
            plugin_name,
        )
    display_name = normalize_plugin_display_name(plugin_name, plugin_data)
    logger.info(
        "Successfully loaded and announced plugin: '%s' (name: %s) v%s - Author: %s",
        display_name,
        plugin_name,
        plugin_data.get("version_soaiplugin", "N/A"),
        plugin_data.get("author_soaiplugin", "Unknown"),
    )
