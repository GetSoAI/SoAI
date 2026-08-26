"""SoAI - Plugin manager startup and reconciliation lifecycle [backend/plugins/manager/lifecycle_startup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exceptions import SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from plugins.manager.alias_map import hydrate_alias_map_from_database
from plugins.manager.internal_protocols import (
    PluginManagerLifecycleSubscriptionsProtocol,
)
from plugins.manager.lifecycle_initialization import initialize_plugin_manager_startup
from plugins.manager.lifecycle_readiness import resolve_readiness_error
from plugins.manager.lifecycle_reconciliation_failures import (
    handle_initial_reconciliation_handled_failure,
    handle_initial_reconciliation_unexpected_failure,
)
from plugins.manager.lifecycle_reconciliation_run import (
    claim_initial_reconciliation_run,
    clear_initial_reconciliation_run,
)
from plugins.manager.lifecycle_reconciliation_wait import (
    wait_for_initial_reconciliation_complete,
)
from plugins.manager.lifecycle_startup_result import (
    mark_initial_reconciliation_cancelled_by_shutdown,
    mark_initial_reconciliation_failed,
    mark_initial_reconciliation_success,
    raise_for_initial_reconciliation_failure,
)
from plugins.registry.reconciliation import reconcile_db_with_filesystem

if TYPE_CHECKING:
    from plugins.manager.internal_protocols import PluginManagerLifecycleTarget

__all__ = ("PluginManagerStartupLifecycle",)

LOGGER_NAME = "SoAI.plugins.manager.lifecycle_startup"


@dataclass(frozen=True, slots=True)
class PluginManagerStartupLifecycleDependencies:
    manager: PluginManagerLifecycleTarget
    command_map: dict[type[Event], Callable[[Event], Awaitable[None]]]
    controller: PluginManagerLifecycleSubscriptionsProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginManagerStartupLifecycleDependencies",
            manager=self.manager,
            command_map=self.command_map,
            controller=self.controller,
        )


class PluginManagerStartupLifecycle:
    def __init__(self, deps: PluginManagerStartupLifecycleDependencies) -> None:
        self._manager = deps.manager
        self._command_map = deps.command_map
        self._controller = deps.controller

    async def require_ready(self) -> None:
        manager = self._manager
        manager.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
        await self.wait_for_initial_reconciliation()
        raise_for_initial_reconciliation_failure(manager)
        error_message = resolve_readiness_error(manager)
        if error_message is not None:
            raise StateError(
                "Plugin manager is not ready.",
                operation="plugin_manager.require_ready",
                details={
                    "fatal_readiness_error": manager.state.lifecycle.fatal_readiness_error,
                    "reconciliation_error": manager.state.lifecycle.initial_reconciliation_error,
                },
            )

    async def wait_for_initial_reconciliation(self, timeout: float | None = None) -> bool:
        return await wait_for_initial_reconciliation_complete(self._manager, timeout)

    async def mark_reconciliation_pending(self) -> None:
        manager = self._manager
        async with manager.state.lifecycle.reconciliation_pending_lock:
            manager.state.lifecycle.reconciliation_pending = True

    async def run_initial_reconciliation(self) -> None:
        logger = get_logger(LOGGER_NAME)
        manager = self._manager
        lifecycle = manager.dependencies.infrastructure.lifecycle
        if lifecycle.disabled:
            mark_initial_reconciliation_success(manager)
            manager.state.lifecycle.initial_reconciliation_complete.set()
            return
        if lifecycle.shutdown_event.is_set():
            mark_initial_reconciliation_cancelled_by_shutdown(manager)
            manager.state.lifecycle.initial_reconciliation_complete.set()
            return
        active_reconciliation_task = await claim_initial_reconciliation_run(manager)
        if active_reconciliation_task is not None:
            logger.debug("Reconciliation already running; waiting for the active run.")
            await active_reconciliation_task
            return
        completed_successfully = False
        try:
            while True:
                async with manager.state.lifecycle.reconciliation_pending_lock:
                    manager.state.lifecycle.reconciliation_pending = False
                await reconcile_db_with_filesystem(manager)
                async with manager.state.lifecycle.reconciliation_pending_lock:
                    if not manager.state.lifecycle.reconciliation_pending:
                        break
                    logger.debug("Reconciliation requested during previous run; re-running.")
            completed_successfully = True
        except asyncio.CancelledError:
            logger.debug("Initial plugin reconciliation task cancelled during shutdown.")
            if not lifecycle.shutdown_event.is_set():
                mark_initial_reconciliation_failed(
                    manager,
                    "Initial plugin reconciliation was cancelled before shutdown.",
                )
            else:
                mark_initial_reconciliation_cancelled_by_shutdown(manager)
            raise
        except RECOVERABLE_EXCEPTIONS as exception:
            await handle_initial_reconciliation_handled_failure(
                manager,
                logger,
                exception,
            )
            raise
        except SoAIError as exception:
            await handle_initial_reconciliation_handled_failure(
                manager,
                logger,
                exception,
            )
            raise
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            await handle_initial_reconciliation_unexpected_failure(
                manager,
                logger,
                exception,
            )
            raise
        finally:
            if completed_successfully:
                mark_initial_reconciliation_success(manager)
            manager.state.lifecycle.initial_reconciliation_complete.set()
            clear_initial_reconciliation_run(manager)

    async def ensure_reconciliation_started(self) -> None:
        logger = get_logger(LOGGER_NAME)
        manager = self._manager
        task_helpers = manager.dependencies.infrastructure.task_helpers
        lifecycle = manager.dependencies.infrastructure.lifecycle
        if lifecycle.disabled:
            logger.debug("Skipping plugin reconciliation start because the service is disabled.")
            return
        if lifecycle.shutdown_event.is_set():
            logger.debug("Skipping plugin reconciliation start during shutdown.")
            return
        async with manager.state.lifecycle.reconciliation_start_lock:
            if lifecycle.disabled:
                logger.debug(
                    "Skipping plugin reconciliation start because the service is disabled.",
                )
                return
            if lifecycle.shutdown_event.is_set():
                logger.debug("Skipping plugin reconciliation start during shutdown.")
                return
            ongoing = manager.state.lifecycle.reconciliation_task
            if ongoing and (not ongoing.done()):
                await self.mark_reconciliation_pending()
                logger.debug("Reconciliation already running; marking re-run pending.")
                return
            logger.debug("Starting plugin reconciliation in the background.")
            manager.state.lifecycle.reconciliation_task = task_helpers.spawn_tracked_task(
                self.run_initial_reconciliation(),
                logger=logger,
                name="plugin-initial-reconciliation",
                cancellation_binder=lifecycle.cancellation_binder,
                cancellation_id=create_system_id(
                    subsystem="plugin_manager",
                    owner="initial_reconciliation",
                    include_random_suffix=False,
                ),
                owner="plugin_manager_reconciliation",
                finalizer_tracker=lifecycle.finalizer_tracker,
            )

    def start_initial_reconciliation(self) -> None:
        logger = get_logger(LOGGER_NAME)
        manager = self._manager
        task_helpers = manager.dependencies.infrastructure.task_helpers
        lifecycle = manager.dependencies.infrastructure.lifecycle
        if lifecycle.disabled:
            logger.debug("Skipping initial plugin reconciliation because the service is disabled.")
            return
        if lifecycle.shutdown_event.is_set():
            logger.debug("Skipping initial plugin reconciliation during shutdown.")
            return
        controller = manager.state.lifecycle.reconciliation_start_task
        if controller and (not controller.done()):
            return

        async def _controller() -> None:
            try:
                await self.ensure_reconciliation_started()
            finally:
                manager.state.lifecycle.reconciliation_start_task = None

        manager.state.lifecycle.reconciliation_start_task = task_helpers.spawn_tracked_task(
            _controller(),
            logger=logger,
            name="plugin-reconciliation-start",
            cancellation_binder=lifecycle.cancellation_binder,
            cancellation_id=create_system_id(
                subsystem="plugin_manager",
                owner="reconciliation_start",
                include_random_suffix=False,
            ),
            owner="plugin_manager_reconciliation_start",
            finalizer_tracker=lifecycle.finalizer_tracker,
        )

    async def initialize(self) -> None:
        await initialize_plugin_manager_startup(
            self._manager,
            self._command_map,
            self._controller,
        )

    async def hydrate_alias_map_from_database(self) -> None:
        await hydrate_alias_map_from_database(self._manager)
