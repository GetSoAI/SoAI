"""SoAI - Orchestrator plugin state tracking and inactivity monitoring [backend/orchestrator/director.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import override

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_models_model_events import ModelLoadedEvent
from core.events.types_models_requests import (
    EmbeddingRequestReceived,
    InferenceRequestReceived,
)
from core.events.types_plugins import StopAllPluginsCommand
from core.lifecycle.protocols import Shutdownable
from core.logging.trace import get_logger
from core.metrics.keyspace_base import (
    INACTIVITY_MONITOR_GAUGE_INACTIVE_MS,
    INACTIVITY_MONITOR_GAUGE_LAST_ACTIVITY,
)
from core.runtime.request_context import create_system_context
from core.runtime.soai_identifiers import create_system_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.timing.epoch import epoch_ms
from orchestrator.inactivity_actions import (
    InactivityWorkflowProfile,
    build_model_inactivity_profile,
    build_system_inactivity_profile,
)
from orchestrator.inactivity_dependencies import InactivityMonitorDependencies
from orchestrator.inactivity_settings import (
    InactivityMonitorSettings,
    resolve_inactivity_monitor_settings,
)
from orchestrator.inactivity_workflow import run_inactivity_workflow

__all__ = ("InactivityMonitor",)

LOGGER_NAME = "SoAI.orchestrator.director"
OPERATION = "orchestrator.director.inactivity_monitor"


class InactivityMonitor(Shutdownable):
    def __init__(self, deps: InactivityMonitorDependencies) -> None:
        self._deps = deps
        self._config_section = deps.config.get("SYSTEM.INACTIVITY", {})
        self._settings = resolve_inactivity_monitor_settings(self._config_section)
        self._system_monitoring_enabled = self._settings.system_enabled
        self._last_activity_time = time.monotonic()
        self._activity_lock = asyncio.Lock()
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._monitor_task: asyncio.Task[None] | None = None
        self._subscriptions_registered = False
        self._lifecycle_lock: asyncio.Lock = asyncio.Lock()
        self._action_in_progress: asyncio.Lock = asyncio.Lock()

    @property
    def settings(self) -> InactivityMonitorSettings:
        return self._settings

    async def start(self) -> None:
        logger = get_logger(LOGGER_NAME)
        async with self._lifecycle_lock:
            current_task = self._monitor_task
            if current_task is not None and current_task.done():
                self._monitor_task = None
            if self._monitor_task is not None:
                logger.debug(
                    "Inactivity monitor start requested while already running; ignoring duplicate start.",
                )
                return None
            system_enabled = self._settings.system_enabled
            if (
                system_enabled
                and self._settings.system_action == "shutdown"
                and (not callable(self._deps.main_shutdown_coro))
            ):
                logger.critical(
                    "Inactivity monitor's shutdown action enabled, but shutdown_coro not provided. Disabling system monitoring.",
                )
                system_enabled = False
            self._system_monitoring_enabled = system_enabled
            if not system_enabled and (not self._settings.models_enabled):
                return logger.info("Inactivity monitor is disabled by configuration.")
            if self._shutdown_event.is_set():
                self._shutdown_event = asyncio.Event()
            if not self._subscriptions_registered:
                for event_type in [
                    InferenceRequestReceived,
                    EmbeddingRequestReceived,
                    ModelLoadedEvent,
                ]:
                    self._deps.event_bus.subscribe(event_type, self._on_activity)
                self._subscriptions_registered = True
            self._monitor_task = spawn_tracked_task(
                self._monitor_loop(),
                name="inactivity-monitor-loop",
                logger=logger,
                cancellation_binder=self._deps.cancellation_binder,
                cancellation_id=create_system_id(
                    subsystem="inactivity_monitor",
                    owner="loop",
                    include_random_suffix=False,
                ),
                owner="inactivity_monitor",
                metadata={"check_interval": self._settings.check_interval_seconds},
                finalizer_tracker=self._deps.finalizer_tracker,
            )
            logger.debug(
                "Inactivity monitor started - System: %s (%.1fm), Models: %s (%.1fm)",
                system_enabled,
                self._settings.system_timeout_seconds / 60,
                self._settings.models_enabled,
                self._settings.models_timeout_seconds / 60,
            )

    @override
    async def shutdown(self) -> None:
        logger = get_logger(LOGGER_NAME)
        async with self._lifecycle_lock:
            if self._shutdown_event.is_set():
                return
            logger.debug("InactivityMonitor shutdown initiated.")
            self._shutdown_event.set()
            monitor_task = self._monitor_task
            self._monitor_task = None
        if monitor_task and (not monitor_task.done()):
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                logger.debug("Inactivity monitor task cancelled during shutdown.")
        logger.debug("Inactivity monitor has been shut down.")

    async def _on_activity(self, _: Event) -> None:
        now = time.monotonic()
        now_epoch_ms = epoch_ms()
        async with self._activity_lock:
            self._last_activity_time = now
        self._deps.metrics_manager.set_gauge(
            *INACTIVITY_MONITOR_GAUGE_LAST_ACTIVITY,
            value=now_epoch_ms,
        )

    async def _monitor_loop(self) -> None:
        logger = get_logger(LOGGER_NAME)
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._settings.check_interval_seconds)
                async with self._activity_lock:
                    last_activity_time = self._last_activity_time
                inactive_duration_seconds = time.monotonic() - last_activity_time
                inactive_duration_ms = int(inactive_duration_seconds * 1000)
                self._deps.metrics_manager.set_gauge(
                    *INACTIVITY_MONITOR_GAUGE_INACTIVE_MS,
                    value=inactive_duration_ms,
                )
                if (
                    self._system_monitoring_enabled
                    and inactive_duration_seconds >= self._settings.system_timeout_seconds
                ):
                    await self._handle_system_inactivity()
                elif (
                    self._settings.models_enabled
                    and inactive_duration_seconds >= self._settings.models_timeout_seconds
                ):
                    await self._handle_model_inactivity()
            except asyncio.CancelledError:
                break
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Error in inactivity monitor loop",
                    operation=OPERATION,
                )

    async def _execute_inactivity_action(
        self,
        timeout: float,
        action_callable: Callable[[], Awaitable[None]],
    ) -> None:
        if self._action_in_progress.locked():
            return
        async with self._action_in_progress:
            async with self._activity_lock:
                last_activity_time = self._last_activity_time
            if time.monotonic() - last_activity_time >= timeout:
                await action_callable()

    async def _run_inactivity_workflow(
        self,
        *,
        profile: InactivityWorkflowProfile,
        finalizer: Callable[[], Awaitable[None]],
    ) -> None:
        await run_inactivity_workflow(
            logger=get_logger(LOGGER_NAME),
            audit_logger=self._deps.audit_logger,
            metrics_manager=self._deps.metrics_manager,
            timeout=profile.timeout_seconds,
            action_spec=profile.action_spec,
            finalizer=finalizer,
            execute_inactivity_action=self._execute_inactivity_action,
        )

    async def _system_inactivity_finalizer(self) -> None:
        logger = get_logger(LOGGER_NAME)
        self._shutdown_event.set()
        _ = spawn_tracked_task(
            self._deps.main_shutdown_coro(),
            name="inactivity-monitor-shutdown",
            logger=logger,
            cancellation_binder=self._deps.cancellation_binder,
            cancellation_id=create_system_id(
                subsystem="inactivity_monitor",
                owner="shutdown",
                include_random_suffix=False,
            ),
            owner="inactivity_shutdown",
            finalizer_tracker=self._deps.finalizer_tracker,
        )

    async def _model_inactivity_finalizer(self) -> None:
        await self._deps.event_bus.publish(
            StopAllPluginsCommand(context=create_system_context("inactivity_unload")),
        )
        async with self._activity_lock:
            self._last_activity_time = time.monotonic()

    async def _handle_system_inactivity(self) -> None:
        profile = build_system_inactivity_profile(self._settings)
        if self._settings.system_action == "shutdown":
            await self._run_inactivity_workflow(
                profile=profile,
                finalizer=self._system_inactivity_finalizer,
            )
            return
        if self._settings.system_action == "unload_models":
            await self._run_inactivity_workflow(
                profile=profile,
                finalizer=self._model_inactivity_finalizer,
            )
            return

    async def _handle_model_inactivity(self) -> None:
        profile = build_model_inactivity_profile(self._settings)
        await self._run_inactivity_workflow(
            profile=profile,
            finalizer=self._model_inactivity_finalizer,
        )
