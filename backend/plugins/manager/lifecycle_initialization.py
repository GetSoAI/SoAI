"""SoAI - Plugin manager startup initialization recovery [backend/plugins/manager/lifecycle_initialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.timing.monotonic import monotonic_ms
from plugins.clone.clone_startup_recovery import recover_interrupted_clone_transactions
from plugins.filesystem.runtime_artifacts import prepare_plugin_runtime_directories
from plugins.manager.alias_map import hydrate_alias_map_from_database
from plugins.manager.inherited_backend_process_recovery import (
    reconcile_inherited_backend_processes,
)
from plugins.manager.lifecycle_bootstrap import register_plugin_manager_subscriptions
from plugins.manager.lifecycle_readiness import publish_readiness_degraded_override
from plugins.manager.startup_backend_process_cleanup import (
    cleanup_startup_tracked_backend_processes,
)
from plugins.manager.startup_recovery import recover_startup_stale_plugin_states

if TYPE_CHECKING:
    from plugins.manager.internal_protocols import (
        PluginManagerLifecycleSubscriptionsProtocol,
        PluginManagerLifecycleTarget,
    )

__all__ = ("initialize_plugin_manager_startup",)

LOGGER_NAME = "SoAI.plugins.manager.lifecycle_initialization"
OPERATION_PLUGIN_MANAGER_INITIALIZE_STARTUP_RECOVERY = "plugin_manager.initialize.startup_recovery"


async def initialize_plugin_manager_startup(
    manager: PluginManagerLifecycleTarget,
    command_map: dict[type[Event], Callable[[Event], Awaitable[None]]],
    controller: PluginManagerLifecycleSubscriptionsProtocol,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if manager.dependencies.models.model_registry is None:
        raise StateError("Plugin manager requires a model registry instance.")
    if not manager.paths.plugin_directory or not manager.paths.backends_directory:
        raise StateError("Plugin and backends directories must be provided.")
    manager.state.lifecycle.fatal_readiness_error = None
    step_started_ms = monotonic_ms()
    await prepare_plugin_runtime_directories(manager, logger)
    logger.debug(
        "Plugin manager startup directory preparation completed in %sms.",
        monotonic_ms() - step_started_ms,
    )
    step_started_ms = monotonic_ms()
    await manager.worker_controller.start()
    logger.debug(
        "Plugin manager worker controller start completed in %sms.",
        monotonic_ms() - step_started_ms,
    )
    step_started_ms = monotonic_ms()
    await hydrate_alias_map_from_database(manager)
    logger.debug(
        "Plugin manager alias map hydration completed in %sms.",
        monotonic_ms() - step_started_ms,
    )
    step_started_ms = monotonic_ms()
    if not controller.subscriptions_registered:
        register_plugin_manager_subscriptions(
            manager,
            command_map,
        )
        controller.subscriptions_registered = True
    logger.debug(
        "Plugin manager subscription registration completed in %sms.",
        monotonic_ms() - step_started_ms,
    )
    try:
        step_started_ms = monotonic_ms()
        recovered_clones = await recover_interrupted_clone_transactions(manager)
        logger.debug(
            "Plugin clone startup recovery completed for %s transaction(s) in %sms.",
            recovered_clones,
            monotonic_ms() - step_started_ms,
        )
        step_started_ms = monotonic_ms()
        inherited_process_count = await reconcile_inherited_backend_processes(
            manager,
            logger=logger,
        )
        logger.debug(
            "Plugin manager inherited backend reconciliation found %s process(es) in %sms.",
            inherited_process_count,
            monotonic_ms() - step_started_ms,
        )
        step_started_ms = monotonic_ms()
        await cleanup_startup_tracked_backend_processes(manager, logger=logger)
        logger.debug(
            "Plugin manager tracked backend cleanup completed in %sms.",
            monotonic_ms() - step_started_ms,
        )
        step_started_ms = monotonic_ms()
        await recover_startup_stale_plugin_states(manager)
        logger.debug(
            "Plugin manager stale state recovery completed in %sms.",
            monotonic_ms() - step_started_ms,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        trace_id = create_system_id(
            subsystem="plugin_startup_recovery",
            owner="failure",
            include_random_suffix=True,
        )
        log_exception(
            logger,
            exception,
            message="Plugin startup recovery failed; plugin subsystem is degraded.",
            trace_id=trace_id,
            operation=OPERATION_PLUGIN_MANAGER_INITIALIZE_STARTUP_RECOVERY,
            level="critical",
        )
        manager.state.lifecycle.fatal_readiness_error = (
            f"{trace_id}: {type(exception).__name__}: {exception}"
        )
        await publish_readiness_degraded_override(
            manager,
            reason="Plugin manager startup recovery failed. Plugin subsystem is degraded.",
        )
        raise StateError("Plugin manager startup recovery failed.") from exception
    logger.debug("PluginManager initialized and subscribed to lifecycle commands.")
