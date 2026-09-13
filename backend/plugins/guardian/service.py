"""SoAI - Plugin health monitoring and auto-healing guardian [backend/plugins/guardian/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import ClassVar, override

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.recent_event_tracker import RecentEventTracker
from core.events.types_base import Event
from core.events.types_plugins import (
    AuthoritativeStateChangeEvent,
    PluginInstallationStateChangedEvent,
    PluginRuntimeStateChangedEvent,
)
from core.logging.trace import get_logger
from core.orchestrator.routing_config import RoutingConfig
from core.plugins.dependencies import PluginGuardianDependencies
from core.plugins.protocols_guardian import (
    DirectorComponentContext,
    PluginGuardianProtocol,
)
from core.runtime.soai_identifiers import create_system_id
from core.state.authoritative_state_ordering import is_stale_authoritative_state_event
from core.state.plugin_state_generation import PluginStateGeneration
from core.state.state_names import (
    ORCH_STATE_ERROR,
    ORCH_STATE_QUARANTINED,
    PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
    PLUGIN_STATE_DELETE_ERROR,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_LOAD_ERROR,
    PLUGIN_STATE_UPDATE_ERROR,
)
from core.validation.numbers import coerce_float_from_json
from plugins.guardian.eligibility import GUARDIAN_LOGGER_NAME
from plugins.guardian_flapping import FLAPPING_HISTORY_CAPACITY, record_state_transition
from plugins.guardian_loop import health_check_loop

__all__ = ("PluginGuardian",)

OPERATION = "plugins.guardian.recover_plugin"


def _new_state_history() -> deque[tuple[str, float]]:
    return deque(maxlen=FLAPPING_HISTORY_CAPACITY)


class PluginGuardian(PluginGuardianProtocol):
    FLAPPING_FAILURE_STATES: ClassVar[frozenset[str]] = frozenset(
        [
            ORCH_STATE_ERROR,
            PLUGIN_STATE_INSTALL_ERROR,
            PLUGIN_STATE_LOAD_ERROR,
            PLUGIN_STATE_UPDATE_ERROR,
            PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
            PLUGIN_STATE_DELETE_ERROR,
        ],
    )

    def __init__(self, deps: PluginGuardianDependencies) -> None:
        self.orchestrator = deps.orchestrator
        self.executor = deps.executor
        self.component_context = deps.component_context
        self.bus = self.component_context.event_bus
        self.plugin_manager = self.component_context.plugin_manager
        self.state_aggregator = self.component_context.state_aggregator
        self.metrics = self.component_context.metrics_manager
        self.audit_logger = self.component_context.audit_logger
        self.routing_config = self.component_context.routing_config
        self.cancellation_binder = self.component_context.cancellation_binder
        self.finalizer_tracker = self.component_context.finalizer_tracker
        self.shutdown_event = asyncio.Event()
        self._health_check_task: asyncio.Task[None] | None = None
        self.recovery_tasks: dict[str, asyncio.Task[None]] = {}
        self.recovery_tasks_lock = asyncio.Lock()
        self.recovery_initiation_lock = asyncio.Lock()
        self.state_history: dict[str, deque[tuple[str, float]]] = defaultdict(_new_state_history)
        self._processed_state_change_events = RecentEventTracker()
        self._subscriptions_registered = False

    @override
    def start(self) -> None:
        logger = get_logger(GUARDIAN_LOGGER_NAME)
        if self.shutdown_event.is_set():
            self.shutdown_event = asyncio.Event()
        if not self._subscriptions_registered:
            self._register_event_subscriptions()
        if not self._health_check_task or self._health_check_task.done():
            self._health_check_task = self.component_context.spawn_tracked_task(
                health_check_loop(self),
                name="plugin-guardian-health",
                logger=logger,
                cancellation_binder=self.cancellation_binder,
                finalizer_tracker=self.finalizer_tracker,
                cancellation_id=create_system_id(
                    subsystem="plugin_guardian",
                    owner="health_check",
                    include_random_suffix=False,
                ),
                owner="plugin_guardian_health",
            )

    @override
    async def stop(self) -> None:
        logger = get_logger(GUARDIAN_LOGGER_NAME)
        self.shutdown_event.set()
        if self._health_check_task:
            await self.component_context.cancel_task(
                self._health_check_task,
                logger=logger,
                label="plugin-guardian-health-check",
            )
            self._health_check_task = None
        async with self.recovery_tasks_lock:
            recovery_tasks_to_cancel = list(self.recovery_tasks.values())
            self.recovery_tasks.clear()
        for task in recovery_tasks_to_cancel:
            await self.component_context.cancel_task(
                task,
                logger=logger,
                label="plugin-guardian-recovery",
            )
        if self._subscriptions_registered:
            self._unregister_event_subscriptions()

    @override
    async def is_plugin_recovering(self, plugin_name: str) -> bool:
        async with self.recovery_tasks_lock:
            return plugin_name in self.recovery_tasks

    @override
    def refresh_config(
        self,
        routing_config: RoutingConfig,
        *,
        component_context: DirectorComponentContext | None = None,
    ) -> None:
        self.routing_config = routing_config
        if component_context:
            self.update_component_context(component_context)

    def _apply_component_context(self, component_context: DirectorComponentContext) -> None:
        self.component_context = component_context
        self.bus = component_context.event_bus
        self.plugin_manager = component_context.plugin_manager
        self.state_aggregator = component_context.state_aggregator
        self.metrics = component_context.metrics_manager
        self.audit_logger = component_context.audit_logger
        self.routing_config = component_context.routing_config
        self.cancellation_binder = component_context.cancellation_binder
        self.finalizer_tracker = component_context.finalizer_tracker

    @override
    def update_component_context(self, component_context: DirectorComponentContext) -> None:
        self._apply_component_context(component_context)
        if self._subscriptions_registered:
            self._unregister_event_subscriptions()
            self._register_event_subscriptions()

    def _register_event_subscriptions(self) -> None:
        self.bus.subscribe(
            PluginRuntimeStateChangedEvent,
            self._handle_runtime_state_change_event,
        )
        self.bus.subscribe(
            PluginInstallationStateChangedEvent,
            self._handle_installation_state_change_event,
        )
        self._subscriptions_registered = True

    def _unregister_event_subscriptions(self) -> None:
        self.bus.unsubscribe(
            PluginRuntimeStateChangedEvent,
            self._handle_runtime_state_change_event,
        )
        self.bus.unsubscribe(
            PluginInstallationStateChangedEvent,
            self._handle_installation_state_change_event,
        )
        self._subscriptions_registered = False

    async def _handle_state_change_event(self, event: AuthoritativeStateChangeEvent) -> None:
        if await self._processed_state_change_events.has_recent(event.event_id):
            return
        current_states = await self.state_aggregator.get_all_plugin_states()
        if is_stale_authoritative_state_event(event, current_states.get(event.plugin_name)):
            return
        record_state_transition(
            self.state_history[event.plugin_name],
            event.new_state,
            observed_at=time.monotonic() - max(0.0, time.time() - event.timestamp),
        )
        await self._processed_state_change_events.mark_processed(event.event_id)

    async def _handle_runtime_state_change_event(self, event: Event) -> None:
        if not isinstance(event, PluginRuntimeStateChangedEvent):
            return
        await self._handle_state_change_event(event)

    async def _handle_installation_state_change_event(self, event: Event) -> None:
        if not isinstance(event, PluginInstallationStateChangedEvent):
            return
        await self._handle_state_change_event(event)

    async def _escalate_to_quarantine(self, plugin_name: str, reason: str) -> None:
        logger = get_logger(GUARDIAN_LOGGER_NAME)
        logger.critical(
            "Escalating plugin '%s' to QUARANTINED state. Reason: %s",
            plugin_name,
            reason,
        )
        self.audit_logger.critical(
            {
                "actor": "system_guardian",
                "action": "RECOVERY_FAILURE_ESCALATION",
                "target": plugin_name,
                "details": {"reason": reason},
            },
        )
        await self.orchestrator.circuit_breakers.trip_circuit_breaker(plugin_name)
        await self.orchestrator.publisher.publish_runtime_state_change(
            plugin_name,
            ORCH_STATE_QUARANTINED,
            reason,
        )

    async def guarded_recover_plugin(
        self,
        plugin_name: str,
        reason: str,
        expected_generation: PluginStateGeneration,
    ) -> None:
        logger = get_logger(GUARDIAN_LOGGER_NAME)
        self.state_history.pop(plugin_name, None)
        recovery_timeout = coerce_float_from_json(
            self.routing_config.health_checks.get("RECOVERY_TIMEOUT_SEC", 1440.0),
            default=1440.0,
            allow_bool=True,
        )
        try:
            await asyncio.wait_for(
                self.orchestrator.recovery.handle_plugin_recovery(
                    plugin_name,
                    reason,
                    expected_generation=expected_generation,
                ),
                timeout=recovery_timeout,
            )
        except TimeoutError:
            await self._escalate_to_quarantine(
                plugin_name,
                f"Recovery process timed out after {recovery_timeout}s.",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Plugin recovery failed.",
                operation=OPERATION,
                details={"plugin_name": plugin_name, "reason": reason},
                level="error",
            )
            await self.orchestrator.publisher.publish_runtime_state_change(
                plugin_name,
                ORCH_STATE_ERROR,
                f"Recovery process failed with an exception: {exception}",
            )
        finally:
            async with self.recovery_tasks_lock:
                if self.recovery_tasks.pop(plugin_name, None):
                    logger.debug("Removed recovery task for '%s' from tracking.", plugin_name)
