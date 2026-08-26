"""SoAI - Plugin config reload lifecycle handler [backend/orchestrator/lifecycle/plugin_config_reload_handler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import override

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.subscriptions import publish_config_apply_event
from core.events.types_system import ConfigReloadedEvent
from core.logging.trace import get_logger
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN,
    SchedulerWorkItem,
)
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_ERROR,
    ORCH_STATE_QUARANTINED,
    ORCH_STATE_STOPPED,
    ORCH_STATE_STOPPING,
    PLUGIN_STATE_INCOMPATIBLE,
    PLUGIN_STATE_PERSISTENT_READY,
    PLUGIN_STATE_STOPPED,
)
from core.state.state_transition_sets import (
    ORCHESTRATOR_STATES,
    PLUGIN_MANAGER_TRANSIENT_STATES,
)
from orchestrator.lifecycle.config_reload_result import (
    PluginConfigReloadOutcome,
    PluginConfigReloadResult,
)
from orchestrator.lifecycle.config_reload_revision_tracker import (
    ConfigReloadRevisionTracker,
)
from orchestrator.lifecycle.plugin_config_reload_persistence import (
    restore_persistent_ready_after_config_reload,
)
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleShutdownCoordinatorProtocol,
)
from orchestrator.lifecycle.shared_dependencies import LifecycleSharedDependencies
from orchestrator.lifecycle.state_transition_publication import (
    publish_runtime_state_change_and_wait,
)

__all__ = (
    "PluginConfigReloadHandler",
    "PluginConfigReloadHandlerDependencies",
)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.plugin_config_reload_handler"
OPERATION = "orchestrator_lifecycle.handle_routing_config_update.reload_plugin_instance"


@dataclass(frozen=True, slots=True)
class PluginConfigReloadHandlerDependencies(LifecycleSharedDependencies):
    shutdown: OrchestratorLifecycleShutdownCoordinatorProtocol

    @override
    def __post_init__(self) -> None:
        LifecycleSharedDependencies.__post_init__(self)
        require_dependencies(
            owner="PluginConfigReloadHandlerDependencies",
            shutdown=self.shutdown,
        )


class PluginConfigReloadHandler:
    def __init__(self, deps: PluginConfigReloadHandlerDependencies) -> None:
        self._deps = deps
        self._revision_tracker = ConfigReloadRevisionTracker()

    async def handle_plugin_config_reloaded(
        self,
        event: ConfigReloadedEvent,
    ) -> PluginConfigReloadResult:
        logger = get_logger(LOGGER_NAME)
        plugin_name = event.config_name
        superseded_result = await self._revision_tracker.record_seen(plugin_name, event.revision)
        if superseded_result is not None:
            return superseded_result
        if not self._deps.orchestrator.plugin_manager.is_known_plugin(plugin_name):
            logger.debug("Ignoring event for unknown or purged plugin '%s'.", plugin_name)
            return PluginConfigReloadResult(PluginConfigReloadOutcome.SUPERSEDED)
        prior_status, preparation_result = await self._prepare_plugin_for_config_reload(event)
        if preparation_result is not None:
            return preparation_result
        if prior_status is None:
            error = "unable to resolve plugin state"
            await self._publish_config_apply_event(event, error)
            return PluginConfigReloadResult(
                PluginConfigReloadOutcome.FAILED_TERMINAL,
                error=error,
            )
        if prior_status not in {PLUGIN_STATE_STOPPED, ORCH_STATE_STOPPED}:
            stopping_state_result = await self._verify_plugin_is_stopping(plugin_name, prior_status)
            if stopping_state_result is not None:
                return stopping_state_result
            stop_result = await self._stop_plugin_for_config_reload(plugin_name)
            if stop_result is not None:
                return stop_result
        reload_result = await self._reload_plugin_and_publish_result(
            plugin_name,
            prior_status,
            event,
        )
        if reload_result.outcome == PluginConfigReloadOutcome.APPLIED:
            await self._revision_tracker.record_applied(plugin_name, event.revision)
        return reload_result

    async def _prepare_plugin_for_config_reload(
        self,
        event: ConfigReloadedEvent,
    ) -> tuple[str | None, PluginConfigReloadResult | None]:
        plugin_name = event.config_name
        if self._deps.shutdown_event.is_set():
            error = "shutdown in progress"
            await self._publish_config_apply_event(event, error)
            return (
                None,
                PluginConfigReloadResult(
                    PluginConfigReloadOutcome.FAILED_TERMINAL,
                    error=error,
                ),
            )
        prior_status = await self._deps.orchestrator.state_aggregator.get_plugin_status(plugin_name)
        if prior_status in PLUGIN_MANAGER_TRANSIENT_STATES:
            return (
                None,
                PluginConfigReloadResult(
                    PluginConfigReloadOutcome.DEFERRED,
                    error=f"plugin in transient state: {prior_status}",
                ),
            )
        if prior_status in {
            ORCH_STATE_DISABLED,
            ORCH_STATE_QUARANTINED,
            PLUGIN_STATE_INCOMPATIBLE,
        }:
            error = f"plugin not reloadable in state: {prior_status}"
            await self._publish_config_apply_event(event, error)
            return (
                None,
                PluginConfigReloadResult(
                    PluginConfigReloadOutcome.FAILED_TERMINAL,
                    error=error,
                ),
            )
        if (
            prior_status != PLUGIN_STATE_PERSISTENT_READY
            and prior_status not in ORCHESTRATOR_STATES
        ):
            error = f"plugin not active: {prior_status}"
            await self._publish_config_apply_event(event, error)
            return (
                None,
                PluginConfigReloadResult(
                    PluginConfigReloadOutcome.FAILED_TERMINAL,
                    error=error,
                ),
            )
        if prior_status in {PLUGIN_STATE_STOPPED, ORCH_STATE_STOPPED}:
            return prior_status, None
        await publish_runtime_state_change_and_wait(
            publisher=self._deps.lifecycle_publisher,
            plugin_name=plugin_name,
            new_state=ORCH_STATE_STOPPING,
            reason=f"Config reload requested: {event.source}",
        )
        return prior_status, None

    async def _verify_plugin_is_stopping(
        self,
        plugin_name: str,
        prior_status: str,
    ) -> PluginConfigReloadResult | None:
        current_status = await self._deps.orchestrator.state_aggregator.get_plugin_status(
            plugin_name,
        )
        if current_status == ORCH_STATE_STOPPING:
            return None
        return PluginConfigReloadResult(
            PluginConfigReloadOutcome.DEFERRED,
            error=f"unable to transition to STOPPING from {prior_status}",
        )

    async def _stop_plugin_for_config_reload(
        self,
        plugin_name: str,
    ) -> PluginConfigReloadResult | None:
        drain_error = await self._deps.shutdown.wait_for_active_tasks_to_drain(plugin_name)
        if drain_error is not None:
            return PluginConfigReloadResult(
                PluginConfigReloadOutcome.FAILED_RETRYABLE,
                error=drain_error,
            )
        stop_outcome = await self._deps.shutdown.perform_plugin_stop_logic(plugin_name)
        if not stop_outcome.terminated:
            await publish_runtime_state_change_and_wait(
                publisher=self._deps.lifecycle_publisher,
                plugin_name=plugin_name,
                new_state=ORCH_STATE_ERROR,
                reason=stop_outcome.message or "Config reload stop failed",
            )
            return PluginConfigReloadResult(
                PluginConfigReloadOutcome.FAILED_RETRYABLE,
                error=stop_outcome.message or "plugin stop failed",
            )
        await publish_runtime_state_change_and_wait(
            publisher=self._deps.lifecycle_publisher,
            plugin_name=plugin_name,
            new_state=ORCH_STATE_STOPPED,
            reason="Plugin stop process completed.",
        )
        return None

    async def _reload_plugin_and_publish_result(
        self,
        plugin_name: str,
        prior_status: str,
        event: ConfigReloadedEvent,
    ) -> PluginConfigReloadResult:
        logger = get_logger(LOGGER_NAME)
        await self._deps.state.reset_plugin_runtime_state(plugin_name)
        try:
            await self._deps.orchestrator.plugin_manager.reload_plugin_instance(plugin_name)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Plugin config reload failed",
                operation=OPERATION,
                details={
                    "plugin_name": plugin_name,
                    "prior_status": prior_status,
                },
                level="warning",
            )
            await publish_runtime_state_change_and_wait(
                publisher=self._deps.lifecycle_publisher,
                plugin_name=plugin_name,
                new_state=ORCH_STATE_ERROR,
                reason=f"Config reload failed: {exception}",
            )
            error = str(exception)
            await self._publish_config_apply_event(event, error)
            return PluginConfigReloadResult(
                PluginConfigReloadOutcome.FAILED_TERMINAL,
                error=error,
            )
        persistent_result = await restore_persistent_ready_after_config_reload(
            plugin_name=plugin_name,
            prior_status=prior_status,
            plugin_manager=self._deps.orchestrator.plugin_manager,
            lifecycle_publisher=self._deps.lifecycle_publisher,
            logger=logger,
        )
        if persistent_result is not None:
            if persistent_result.error is not None:
                await self._publish_config_apply_event(event, persistent_result.error)
            return persistent_result
        await self._publish_config_apply_event(event)
        return PluginConfigReloadResult(
            PluginConfigReloadOutcome.APPLIED,
            work_items=(SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN, plugin_name),),
        )

    async def _publish_config_apply_event(
        self,
        event: ConfigReloadedEvent,
        error: str | None = None,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        await publish_config_apply_event(
            self._deps.orchestrator.bus,
            event,
            error=error,
            logger=logger,
            operation="orchestrator.publish_config_apply",
            message=f"Failed to publish config apply event for '{event.config_name}'",
        )

    async def publish_config_apply_failure(
        self,
        event: ConfigReloadedEvent,
        error: str,
    ) -> None:
        await self._publish_config_apply_event(event, error)
