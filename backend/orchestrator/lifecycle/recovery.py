"""SoAI - Orchestrator recovery workflow (auto-healing) [backend/orchestrator/lifecycle/recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.models.discovery_trigger import publish_model_discovery_request
from core.orchestrator.protocols_lifecycle import (
    OrchestratorCircuitBreakersProtocol,
    OrchestratorLifecyclePublisherProtocol,
)
from core.plugins.persistent_runtime_truth import resolve_persistent_runtime_state
from core.runtime.request_context import create_system_context
from core.state.state_names import (
    ORCH_STATE_ERROR,
    ORCH_STATE_QUARANTINED,
)
from core.state.state_transition_sets import OPERATIONAL_ERROR_STATES
from core.tasks.protocols import RecoveryQueuePurgeProtocol
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleRuntimeMutationsProtocol,
    OrchestratorLifecycleShutdownCoordinatorProtocol,
)
from orchestrator.lifecycle.state_access.internal_protocols import (
    LifecycleStateAccessorProtocol,
)
from orchestrator.types import OrchestratorDependencies

__all__ = (
    "OrchestratorLifecycleRecovery",
    "OrchestratorLifecycleRecoveryDependencies",
)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.recovery"
OPERATION = "orchestrator.recovery_purge"


@dataclass(frozen=True, slots=True)
class OrchestratorLifecycleRecoveryDependencies:
    orchestrator: OrchestratorDependencies
    state: LifecycleStateAccessorProtocol
    lifecycle_publisher: OrchestratorLifecyclePublisherProtocol
    circuit_breakers: OrchestratorCircuitBreakersProtocol
    shutdown: OrchestratorLifecycleShutdownCoordinatorProtocol
    max_recovery_attempts: int

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorLifecycleRecoveryDependencies",
            circuit_breakers=self.circuit_breakers,
            lifecycle_publisher=self.lifecycle_publisher,
            max_recovery_attempts=self.max_recovery_attempts,
            orchestrator=self.orchestrator,
            shutdown=self.shutdown,
            state=self.state,
        )


class OrchestratorLifecycleRecovery:
    def __init__(self, deps: OrchestratorLifecycleRecoveryDependencies) -> None:
        self._deps = deps
        self._max_recovery_attempts = deps.max_recovery_attempts
        self._queue_purge: RecoveryQueuePurgeProtocol | None = None
        self._runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol | None = None

    def update_config(self, max_recovery_attempts: int) -> None:
        self._max_recovery_attempts = max_recovery_attempts

    def bind_runtime_mutations(
        self,
        runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol,
    ) -> None:
        self._runtime_mutations = runtime_mutations

    def bind_queue_purge(self, purge_callback: RecoveryQueuePurgeProtocol) -> None:
        self._queue_purge = purge_callback

    async def purge_plugin_tasks(self, plugin_name: str, reason: str) -> None:
        logger = get_logger(LOGGER_NAME)
        if self._queue_purge is None:
            logger.warning(
                "Queue purge callback not bound; skipping task purge for plugin '%s'.",
                plugin_name,
            )
            return
        purge_reason = f"Recovery initiated for plugin '{plugin_name}': {reason}"
        try:
            await self._queue_purge(plugin_name=plugin_name, reason=purge_reason)
            logger.info(
                "Purged queued and active tasks for plugin '%s' before recovery.",
                plugin_name,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=f"Failed to purge tasks for plugin '{plugin_name}' during recovery",
                operation=OPERATION,
            )

    async def handle_plugin_recovery(self, plugin_name: str, reason: str) -> None:
        runtime_mutations = self._runtime_mutations
        if runtime_mutations is None:
            raise StateError(
                "Runtime mutations must be bound before use.",
                operation="orchestrator.lifecycle.recovery.handle_plugin_recovery",
            )
        await runtime_mutations.submit_recovery(plugin_name, reason)

    async def execute_plugin_recovery(self, plugin_name: str, reason: str) -> None:
        logger = get_logger(LOGGER_NAME)
        logger.info("Attempting recovery for plugin %s: %s", plugin_name, reason)
        lifecycle = self._deps.orchestrator.plugin_manager.lifecycle
        async with lifecycle.plugin_lock_scope(plugin_name):
            await self.purge_plugin_tasks(plugin_name, reason)
            attempt_count = await self._deps.state.increment_recovery_attempts(plugin_name)
            plugin_status = await self._deps.orchestrator.state_aggregator.get_plugin_status(
                plugin_name,
            )
            plugin_instance = await self._deps.orchestrator.plugin_manager.get_plugin_instance(
                plugin_name,
            )
            persistent_runtime = bool(plugin_instance and plugin_instance.PERSISTENT)
            requires_stop = (not persistent_runtime) or plugin_status in OPERATIONAL_ERROR_STATES
            if attempt_count > self._max_recovery_attempts:
                logger.warning(
                    "Plugin %s exceeded max recovery attempts (%s). Tripping circuit breaker.",
                    plugin_name,
                    self._max_recovery_attempts,
                )
                quarantine_reason = (
                    f"Quarantined after {self._max_recovery_attempts} failed recovery attempts."
                )
                if requires_stop:
                    stop_outcome = await self._deps.shutdown.stop_plugin(
                        plugin_name,
                        reason="Stopping after recovery attempts were exhausted.",
                        publish_state_changes=True,
                        wait_for_state_changes=True,
                        force=True,
                    )
                    if not stop_outcome.terminated:
                        logger.error(
                            "Plugin '%s' could not be terminated after recovery attempts were exhausted.",
                            plugin_name,
                        )
                        quarantine_reason = (
                            f"Quarantined after {self._max_recovery_attempts} failed recovery "
                            "attempts. Physical runtime cleanup failed; the backend may still be "
                            "running."
                        )
                await self._deps.circuit_breakers.trip_circuit_breaker(plugin_name)
                await self._deps.lifecycle_publisher.publish_runtime_state_change(
                    plugin_name,
                    ORCH_STATE_QUARANTINED,
                    quarantine_reason,
                )
                await self._deps.state.pop_recovery_attempts(plugin_name)
                return

            if (
                plugin_instance is not None
                and bool(plugin_instance.PERSISTENT)
                and not requires_stop
            ):
                target_state, target_reason, _ = await resolve_persistent_runtime_state(
                    plugin_instance,
                    attempt_activate=True,
                    failure_state=ORCH_STATE_ERROR,
                    operation="orchestrator.recovery.persistent",
                    logger=logger,
                )
                if target_state == ORCH_STATE_ERROR:
                    logger.warning(
                        "Persistent plugin '%s' recovery failed health validation: %s",
                        plugin_name,
                        target_reason,
                    )
                else:
                    logger.info(
                        "Persistent plugin '%s' recovery resolved to %s.",
                        plugin_name,
                        target_state,
                    )
                    await self._deps.state.pop_recovery_attempts(plugin_name)
                    await self._deps.circuit_breakers.record_cb_success(plugin_name)
                await self._deps.lifecycle_publisher.publish_runtime_state_change(
                    plugin_name,
                    target_state,
                    f"Recovery initiated for persistent plugin: {reason}. {target_reason}",
                )
                return

            stop_outcome = await self._deps.shutdown.stop_plugin(
                plugin_name,
                reason=f"Stopping for recovery: {reason}",
                publish_state_changes=True,
                wait_for_state_changes=True,
                force=True,
            )
            if not stop_outcome.terminated:
                logger.error(
                    "Plugin '%s' could not be terminated during recovery.",
                    plugin_name,
                )
                return
            logger.info(
                "Plugin %s stopped for recovery. Triggering model discovery to re-activate models.",
                plugin_name,
            )
            await publish_model_discovery_request(
                self._deps.orchestrator.bus,
                plugins_to_scan=[plugin_name],
                context=create_system_context("recovery"),
            )
