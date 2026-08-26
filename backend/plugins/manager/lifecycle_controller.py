"""SoAI - Plugin manager lifecycle orchestration controller [backend/plugins/manager/lifecycle_controller.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.errors.exceptions import StateError
from core.events.subscriptions import unsubscribe_many
from core.events.types_base import Event
from core.events.types_tasks import CancelTaskCommand
from core.logging.trace import get_logger
from core.runtime.startup_status import StartupPhaseResult
from core.tasks.cancellation_commands import cancel_via_registry
from core.timing.constants import CONTROL_TIMEOUT_SEC
from plugins.manager.command_map import build_plugin_command_map
from plugins.manager.internal_protocols import PluginManagerLifecycleTarget
from plugins.manager.lifecycle_startup import PluginManagerStartupLifecycle
from plugins.manager.lifecycle_startup_result import (
    mark_initial_reconciliation_cancelled_by_shutdown,
)

__all__ = ("PluginManagerLifecycleController",)

LOGGER_NAME = "SoAI.plugins.manager.lifecycle_controller"


class PluginManagerLifecycleController:
    __slots__ = (
        "_begun",
        "_command_map",
        "_finalized",
        "_manager",
        "_shutdown_lock",
        "_startup_lifecycle",
        "_subscriptions_registered",
    )

    def __init__(self, manager: PluginManagerLifecycleTarget) -> None:
        self._manager = manager
        self._command_map: dict[type[Event], Callable[[Event], Awaitable[None]]] = (
            build_plugin_command_map(manager)
        )
        self._subscriptions_registered = False
        self._begun = False
        self._finalized = False
        self._shutdown_lock = asyncio.Lock()
        self._startup_lifecycle: PluginManagerStartupLifecycle | None = None

    @property
    def command_map(self) -> dict[type[Event], Callable[[Event], Awaitable[None]]]:
        return self._command_map

    def attach_startup_lifecycle(self, startup_lifecycle: PluginManagerStartupLifecycle) -> None:
        self._startup_lifecycle = startup_lifecycle

    def _require_startup_lifecycle(self) -> PluginManagerStartupLifecycle:
        startup_lifecycle = self._startup_lifecycle
        if startup_lifecycle is None:
            raise StateError("Plugin manager startup lifecycle is not attached.")
        return startup_lifecycle

    @property
    def subscriptions_registered(self) -> bool:
        return self._subscriptions_registered

    @subscriptions_registered.setter
    def subscriptions_registered(self, value: bool) -> None:
        self._subscriptions_registered = value

    async def require_ready(self) -> None:
        await self._require_startup_lifecycle().require_ready()

    @property
    def initial_reconciliation_result(self) -> StartupPhaseResult:
        return self._manager.state.lifecycle.initial_reconciliation_result

    async def wait_for_initial_reconciliation(self, timeout: float | None = None) -> bool:
        return await self._require_startup_lifecycle().wait_for_initial_reconciliation(timeout)

    async def mark_reconciliation_pending(self) -> None:
        await self._require_startup_lifecycle().mark_reconciliation_pending()

    async def run_initial_reconciliation(self) -> None:
        await self._require_startup_lifecycle().run_initial_reconciliation()

    async def ensure_reconciliation_started(self) -> None:
        await self._require_startup_lifecycle().ensure_reconciliation_started()

    def start_initial_reconciliation(self) -> None:
        self._require_startup_lifecycle().start_initial_reconciliation()

    async def initialize(self) -> None:
        async with self._shutdown_lock:
            manager = self._manager
            shutdown_event = manager.dependencies.infrastructure.lifecycle.shutdown_event
            if self._begun or self._finalized or shutdown_event.is_set():
                raise StateError("Plugin manager cannot initialize after shutdown has started.")
            await self._require_startup_lifecycle().initialize()

    async def handle_cancel_task(self, command: Event) -> None:
        logger = get_logger(LOGGER_NAME)
        manager = self._manager
        if not isinstance(command, CancelTaskCommand):
            return
        manager.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
        cancel_args = await cancel_via_registry(
            command,
            manager.dependencies.infrastructure.lifecycle.cancellation_coordinator,
            manager.dependencies.infrastructure.lifecycle.cancellation_history,
        )
        if cancel_args:
            cancellation_id, reason = cancel_args
            logger.debug(
                "Cancellation propagated via registry for task [%s] (%s).",
                cancellation_id,
                reason,
            )

    async def begin_shutdown(self) -> None:
        async with self._shutdown_lock:
            await self._begin_shutdown_unlocked()

    async def _begin_shutdown_unlocked(self) -> None:
        logger = get_logger(LOGGER_NAME)
        manager = self._manager
        if self._begun:
            return
        logger.debug("PluginManager shutdown quiesce initiated.")
        manager.dependencies.infrastructure.lifecycle.shutdown_event.set()
        if self._subscriptions_registered:
            unsubscribe_many(manager.dependencies.infrastructure.event_bus, self._command_map)
            self._subscriptions_registered = False
        cancelled_count = (
            await manager.dependencies.infrastructure.lifecycle.cancel_all_plugin_tasks(
                "SoAI is shutting down.",
                drain_timeout_sec=CONTROL_TIMEOUT_SEC,
            )
        )
        if cancelled_count:
            logger.info(
                "Cancelled %s active plugin lifecycle task(s) during shutdown.",
                cancelled_count,
            )
        reconciliation_task = manager.state.lifecycle.reconciliation_task
        if reconciliation_task and (not reconciliation_task.done()):
            reconciliation_task.cancel()
            try:
                await reconciliation_task
            except asyncio.CancelledError:
                logger.debug("Initial plugin reconciliation task cancelled during shutdown.")
        reconciliation_start_task = manager.state.lifecycle.reconciliation_start_task
        if reconciliation_start_task and (not reconciliation_start_task.done()):
            reconciliation_start_task.cancel()
            try:
                await reconciliation_start_task
            except asyncio.CancelledError:
                logger.debug("Plugin reconciliation startup controller cancelled during shutdown.")
        if not manager.state.lifecycle.initial_reconciliation_complete.is_set():
            mark_initial_reconciliation_cancelled_by_shutdown(manager)
        manager.state.lifecycle.initial_reconciliation_complete.set()
        self._begun = True
        logger.debug("PluginManager shutdown quiesce completed.")

    async def finalize_shutdown(self) -> None:
        async with self._shutdown_lock:
            await self._finalize_shutdown_unlocked()

    async def _finalize_shutdown_unlocked(self) -> None:
        logger = get_logger(LOGGER_NAME)
        manager = self._manager
        if self._finalized:
            return
        await self._begin_shutdown_unlocked()
        logger.debug("PluginManager worker shutdown initiated.")
        await manager.worker_controller.shutdown()
        self._finalized = True
        logger.debug("PluginManager has been shut down.")

    async def shutdown(self) -> None:
        async with self._shutdown_lock:
            await self._begin_shutdown_unlocked()
            await self._finalize_shutdown_unlocked()

    async def hydrate_alias_map_from_database(self) -> None:
        await self._require_startup_lifecycle().hydrate_alias_map_from_database()
