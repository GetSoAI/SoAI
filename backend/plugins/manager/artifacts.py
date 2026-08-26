"""SoAI - Plugin artifact removal and purge from memory [backend/plugins/manager/artifacts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_waiting import (
    EventPublicationReceipt,
    publication_completion_deadline,
)
from core.events.types_plugins import PluginPurgedEvent, PluginUnloadedEvent
from core.logging.trace import get_logger
from core.state.state_transition_sets import ACTIVE_RESOURCE_STATES
from plugins.manager.alias_map import update_alias_map
from plugins.manager.instances import clear_loaded_plugin_state
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "purge_plugin_from_memory",
    "teardown_plugin_runtime",
)

LOGGER_NAME = "SoAI.plugins.manager.artifacts"
OPERATION_PLUGIN_MANAGER_TEARDOWN_PLUGIN_RUNTIME = "plugin_manager.teardown_plugin_runtime"
OPERATION_PLUGIN_MANAGER_TEARDOWN_PLUGIN_RUNTIME_STOP = (
    "plugin_manager.teardown_plugin_runtime.stop"
)


async def teardown_plugin_runtime(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    clear_display_name_cache: bool,
    update_aliases: bool,
) -> None:
    logger = get_logger(LOGGER_NAME)
    stop_failure: BaseException | None = None
    try:
        current_state = await self.dependencies.infrastructure.state_aggregator.get_plugin_status(
            plugin_name,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to retrieve current plugin state before teardown (non-critical).",
            operation=OPERATION_PLUGIN_MANAGER_TEARDOWN_PLUGIN_RUNTIME,
            details={"plugin_name": plugin_name},
            level="debug",
        )
        current_state = None
    if current_state in ACTIVE_RESOURCE_STATES:
        instance = await self.get_plugin_instance(plugin_name)
        if instance:
            try:
                logger.info(
                    "Stopping plugin '%s' before tearing down runtime state.",
                    plugin_name,
                )
                stop_result = await instance.stop()
                if not stop_result:
                    raise StateError(
                        "Plugin stop returned an unsuccessful result during teardown.",
                        operation=OPERATION_PLUGIN_MANAGER_TEARDOWN_PLUGIN_RUNTIME_STOP,
                        details={"plugin_name": plugin_name},
                    )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message=f"Failed to stop plugin '{plugin_name}' during teardown.",
                    operation=OPERATION_PLUGIN_MANAGER_TEARDOWN_PLUGIN_RUNTIME_STOP,
                    level="error",
                )
                stop_failure = exception
    if clear_display_name_cache:
        async with self.state.validation.display_name_cache_lock:
            self.state.validation.display_name_cache.pop(plugin_name, None)
    await self.dependencies.models.parameter_manager.unregister_plugin_parameters(plugin_name)
    if self.dependencies.core.log_manager is not None:
        await asyncio.to_thread(
            self.dependencies.core.log_manager.detach_streaming_handler_from_plugin,
            plugin_name,
        )
    await clear_loaded_plugin_state(self, plugin_name)
    if update_aliases:
        await update_alias_map(self)
    if stop_failure is not None:
        raise StateError(
            "Plugin runtime was force-cleared after teardown stop failed.",
            operation=OPERATION_PLUGIN_MANAGER_TEARDOWN_PLUGIN_RUNTIME_STOP,
            details={"plugin_name": plugin_name},
        ) from stop_failure


async def purge_plugin_from_memory(self: PluginManagerRuntimeProtocol, plugin_name: str) -> None:
    logger = get_logger(LOGGER_NAME)
    display_name = await self.get_plugin_display_name(plugin_name)
    logger.debug("Purging plugin '%s' (%s) from memory.", display_name, plugin_name)
    orchestrator_lifecycle = self.orchestrator_lifecycle
    if orchestrator_lifecycle is not None:
        await orchestrator_lifecycle.recovery.purge_plugin_tasks(
            plugin_name,
            f"Plugin '{plugin_name}' is being purged from memory.",
        )
    unloaded_event = PluginUnloadedEvent(plugin_name=plugin_name)
    unloaded_receipt = EventPublicationReceipt.create(
        event_type=type(unloaded_event).__name__,
        operation="plugins.manager.artifacts.purge_plugin_from_memory.publish_unloaded",
    )
    await self.dependencies.infrastructure.event_bus.publish(
        unloaded_event,
        wait_for_completion=unloaded_receipt.completion_signal,
    )
    await unloaded_receipt.wait_for_completion(publication_completion_deadline())
    await teardown_plugin_runtime(
        self,
        plugin_name,
        clear_display_name_cache=True,
        update_aliases=True,
    )
    purged_event = PluginPurgedEvent(plugin_name=plugin_name)
    purged_receipt = EventPublicationReceipt.create(
        event_type=type(purged_event).__name__,
        operation="plugins.manager.artifacts.purge_plugin_from_memory.publish_purged",
    )
    await self.dependencies.infrastructure.event_bus.publish(
        purged_event,
        wait_for_completion=purged_receipt.completion_signal,
    )
    await purged_receipt.wait_for_completion(publication_completion_deadline())
    logger.info(
        "Successfully purged plugin '%s' (%s) from memory.",
        display_name,
        plugin_name,
    )
