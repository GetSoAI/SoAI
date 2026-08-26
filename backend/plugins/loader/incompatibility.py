"""SoAI - Marking plugins incompatible and propagating incompatibility [backend/plugins/loader/incompatibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.plugins.errors import PluginIncompatibleError
from core.state.compatibility import CompatibilityInfo, IncompatibilityReason
from core.state.state_names import PLUGIN_STATE_INCOMPATIBLE, PLUGIN_STATE_NOT_DETECTED
from plugins.identity import normalize_plugin_display_name
from plugins.loader.record_data import build_plugin_record_data
from plugins.manager.alias_map import update_alias_map
from plugins.manager.instances import clear_loaded_plugin_state
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.compatibility import build_compatibility_info
from plugins.state.publication_wait import wait_for_plugin_state_publication
from plugins.state.transition_logging import log_skipped_same_state_transition

if TYPE_CHECKING:
    from core.state.state_names import PluginRuntimeStateName
    from core.types.json import JSONDict

__all__ = (
    "handle_incompatible_plugin",
    "handle_plugin_compatibility_failure",
    "propagate_incompatibility_to_dependents",
)

LOGGER_NAME = "SoAI.plugins.loader.incompatibility"
OPERATION = "plugin_loader.handle_incompatible_plugin"
OPERATION_PLUGIN_MANIFEST_EXTRACTION = "plugins.loader.incompatibility.extract_plugin_manifest"


async def handle_incompatible_plugin(
    manager: PluginManagerRuntimeProtocol,
    error: PluginIncompatibleError,
    *,
    plugin_data_override: JSONDict | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    plugin_name = error.plugin_name
    compatibility = error.compatibility
    message = compatibility.message or "Plugin marked as incompatible."
    if plugin_data_override is not None:
        plugin_data = await build_plugin_record_data(
            manager,
            plugin_name,
            plugin_data_override=plugin_data_override,
        )
    else:
        raise StateError(
            f"Cannot persist incompatibility for '{plugin_name}' without plugin metadata.",
        )
    await manager.dependencies.databases.plugins.add_or_update_plugin(
        plugin_data,
        incompatibility=compatibility,
        override=compatibility.is_overridden,
    )
    await clear_loaded_plugin_state(manager, plugin_name)
    async with manager.state.validation.display_name_cache_lock:
        manager.state.validation.display_name_cache[plugin_name] = normalize_plugin_display_name(
            plugin_name,
            plugin_data,
        )
    previous_state: PluginRuntimeStateName = PLUGIN_STATE_NOT_DETECTED
    if manager.dependencies.infrastructure.state_aggregator is not None:
        try:
            previous_state = (
                await manager.dependencies.infrastructure.state_aggregator.get_plugin_status(
                    plugin_name,
                )
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to retrieve previous state for plugin",
                operation=OPERATION,
                details={"plugin_name": plugin_name},
                level="warning",
            )
        await manager.dependencies.infrastructure.state_aggregator.clear_purged_status(plugin_name)
    if previous_state != PLUGIN_STATE_INCOMPATIBLE:
        try:
            receipt = await manager.transition_plugin_manager_state(
                plugin_name,
                PLUGIN_STATE_INCOMPATIBLE,
                message,
            )
            await wait_for_plugin_state_publication(receipt)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to publish installation state change for incompatible plugin",
                operation=OPERATION,
                details={"plugin_name": plugin_name},
                level="warning",
            )
    else:
        log_skipped_same_state_transition(
            logger,
            plugin_name,
            previous_state,
            PLUGIN_STATE_INCOMPATIBLE,
        )
    await update_alias_map(manager)
    logger.warning("Plugin '%s' is incompatible: %s", plugin_name, message)


async def handle_plugin_compatibility_failure(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    compatibility: CompatibilityInfo,
    *,
    plugin_class_name: str | None,
    plugin_data_override: JSONDict,
) -> None:
    await handle_incompatible_plugin(
        manager,
        PluginIncompatibleError(
            plugin_name,
            compatibility,
            plugin_class_name=plugin_class_name,
        ),
        plugin_data_override=plugin_data_override,
    )


async def propagate_incompatibility_to_dependents(
    manager: PluginManagerRuntimeProtocol,
    initially_incompatible_plugins: set[str],
    class_names_by_plugin: dict[str, str | None],
    declared_dependencies_by_plugin: dict[str, list[str]],
) -> set[str]:
    all_incompatible_plugins = set(initially_incompatible_plugins)
    plugins_to_propagate = set(initially_incompatible_plugins)

    while plugins_to_propagate:
        newly_incompatible: set[str] = set()
        for (
            plugin_name,
            declared_dependencies,
        ) in declared_dependencies_by_plugin.items():
            if plugin_name in all_incompatible_plugins:
                continue
            incompatible_dependencies = [
                dependency_name
                for dependency_name in declared_dependencies
                if dependency_name in plugins_to_propagate
            ]
            if incompatible_dependencies:
                newly_incompatible.add(plugin_name)
                compatibility = build_compatibility_info(
                    IncompatibilityReason.DEPENDENCY_MISSING,
                    f"Depends on incompatible plugin(s): {', '.join(sorted(incompatible_dependencies))}.",
                    {
                        "missing_dependencies": sorted(incompatible_dependencies),
                        "declared_dependencies": sorted(declared_dependencies),
                    },
                    False,
                )
                await handle_plugin_compatibility_failure(
                    manager,
                    plugin_name,
                    compatibility,
                    plugin_class_name=class_names_by_plugin.get(plugin_name),
                    plugin_data_override=await build_plugin_record_data(
                        manager,
                        plugin_name,
                        operation=OPERATION_PLUGIN_MANIFEST_EXTRACTION,
                        error_message=(
                            "Cannot persist incompatibility for plugin: manifest could not be read "
                            "(non-critical)."
                        ),
                    ),
                )
        all_incompatible_plugins.update(newly_incompatible)
        plugins_to_propagate = newly_incompatible

    return all_incompatible_plugins
