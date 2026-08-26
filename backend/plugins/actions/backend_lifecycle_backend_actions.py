"""SoAI - Plugin backend action execution and success finalization [backend/plugins/actions/backend_lifecycle_backend_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAITimeoutError, ValidationError
from core.events.completion_waiting import await_publication_receipt
from core.events.types_plugins import (
    InstallPluginBackendCommand,
    RemovePluginBackendCommand,
    UpdatePluginBackendCommand,
)
from core.logging.protocols import LoggerProtocol
from core.models.discovery_trigger import publish_model_discovery_request
from core.plugins.backend_variant_ids import require_backend_variant_id
from core.plugins.persistent_runtime_truth import resolve_persistent_runtime_state
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.runtime.request_context import RequestContext
from core.state.state_names import PLUGIN_STATE_STOPPED
from plugins.filesystem.managed_models import remove_plugin_managed_models
from plugins.manager.capability_support import supports_plugin_capability_from_instance
from plugins.manager.instance_loading import load_plugin_instance
from plugins.manager.policy import LifecycleActionPolicy
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = ()

OPERATION_BASELINE_REFRESH_TIMEOUT = "plugins.actions.backend_lifecycle.baseline_refresh_timeout"


async def execute_backend_action(
    *,
    action: str,
    command: InstallPluginBackendCommand | UpdatePluginBackendCommand | RemovePluginBackendCommand,
    plugin_instance: PluginInstanceProtocol,
    output_callback: Callable[[str], Awaitable[None] | None],
) -> bool:
    if action == "install_backend":
        if not isinstance(command, InstallPluginBackendCommand):
            raise ValidationError(f"Invalid command for action '{action}'.")
        variant_id = require_backend_variant_id(command.backend_variant_id)
        return await plugin_instance.install_backend(output_callback, variant_id)
    if action == "update_backend":
        if not isinstance(command, UpdatePluginBackendCommand):
            raise ValidationError(f"Invalid command for action '{action}'.")
        variant_id = require_backend_variant_id(command.backend_variant_id)
        return await plugin_instance.update_backend(output_callback, variant_id)
    if action == "remove_backend":
        if not isinstance(command, RemovePluginBackendCommand):
            raise ValidationError(f"Invalid command for action '{action}'.")
        return await plugin_instance.remove_backend(output_callback, command.delete_models)
    raise ValidationError(f"Invalid action '{action}'.")


async def finalize_successful_model_removal(
    manager: PluginManagerRuntimeProtocol,
    command: RemovePluginBackendCommand,
) -> None:
    if not command.delete_models:
        return
    await remove_plugin_managed_models(manager, command.plugin_name)
    await manager.dependencies.models.model_database_purge_service.purge_models_for_plugin(
        command.plugin_name,
        manager.lifecycle,
    )


async def finalize_successful_backend_action(
    *,
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    action: str,
    display_name: str,
    context: RequestContext | None,
    action_config: LifecycleActionPolicy,
    plugin_instance: PluginInstanceProtocol,
    logger: LoggerProtocol,
) -> None:
    instance = await manager.get_plugin_instance(plugin_name)
    final_state = action_config.final
    if instance is not None and instance.PERSISTENT and action_config.final == PLUGIN_STATE_STOPPED:
        final_state, _, _ = await resolve_persistent_runtime_state(
            instance,
            attempt_activate=True,
            operation=f"plugin_flow.execute_lifecycle_task.{action}.persistent",
            logger=logger,
        )
    receipt = await manager.transition_plugin_manager_state(
        plugin_name,
        final_state,
        f"Action '{action}' completed successfully.",
        context,
    )
    await await_publication_receipt(receipt)
    if supports_plugin_capability_from_instance(plugin_instance, "SUPPORTS_CONFIGURATION"):
        logger.info(
            "Proactively updating configuration baseline for '%s' after '%s' action.",
            display_name,
            action,
        )
        try:
            await manager.dependencies.infrastructure.config_manager.rescan_and_update_baseline_for_config(
                plugin_name,
            )
        except SoAITimeoutError as exception:
            log_handled_exception(
                logger,
                exception,
                message="Configuration baseline refresh deferred after backend action lock contention.",
                operation=OPERATION_BASELINE_REFRESH_TIMEOUT,
                details={"plugin_name": plugin_name, "action": action},
                level="warning",
            )
    if action in ["install_backend", "update_backend"]:
        await load_plugin_instance(manager, plugin_name, force_reload=True)
        logger.info(
            "Backend action '%s' for '%s' successful. Triggering model discovery.",
            action,
            display_name,
        )
        await publish_model_discovery_request(
            manager.dependencies.infrastructure.event_bus,
            plugins_to_scan=[plugin_name],
            context=context,
        )
