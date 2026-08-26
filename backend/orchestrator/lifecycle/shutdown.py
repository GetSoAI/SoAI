"""SoAI - Orchestrator plugin graceful shutdown and force stop operations [backend/orchestrator/lifecycle/shutdown.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.orchestrator.stop_outcome import PluginStopOutcome
from core.tasks.protocols import TaskRegistryProtocol
from core.timing.constants import CONTROL_TIMEOUT_SEC, MODERATE_DELAY_SEC
from orchestrator.internal_protocols import OrchestratorCapacityProtocol
from orchestrator.lifecycle.runtime_mutation_commands import RuntimeMutationStopRequest
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleRuntimeMutationsProtocol,
)
from orchestrator.lifecycle.shared_dependencies import LifecycleSharedDependencies
from orchestrator.lifecycle.shutdown_request_execution import (
    execute_stop_plugin_request,
)
from orchestrator.lifecycle.shutdown_stop_logic import perform_plugin_stop_logic

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "OrchestratorLifecycleShutdown",
    "OrchestratorLifecycleShutdownDependencies",
)

SHUTDOWN_LOCK_ACQUIRE_BUDGET_FRACTION = 0.25


@dataclass(frozen=True, slots=True)
class OrchestratorLifecycleShutdownDependencies(LifecycleSharedDependencies):
    capacity: OrchestratorCapacityProtocol
    task_registry: TaskRegistryProtocol
    health_check_config: JSONDict

    @override
    def __post_init__(self) -> None:
        LifecycleSharedDependencies.__post_init__(self)
        require_dependencies(
            owner="OrchestratorLifecycleShutdownDependencies",
            capacity=self.capacity,
            health_check_config=self.health_check_config,
            task_registry=self.task_registry,
        )


class OrchestratorLifecycleShutdown:
    _MAX_DRAIN_WAIT_ITERATIONS = 1200

    def __init__(self, deps: OrchestratorLifecycleShutdownDependencies) -> None:
        self._deps = deps
        self._health_check_config = deps.health_check_config
        self._runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol | None = None

    def update_config(self, config: OrchestratorRuntimeConfig) -> None:
        self._health_check_config = config.health_check_config

    def bind_runtime_mutations(
        self,
        runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol,
    ) -> None:
        self._runtime_mutations = runtime_mutations

    async def stop_plugin(
        self,
        plugin_name: str,
        *,
        reason: str = "Plugin stop requested",
        reply_channel: asyncio.Queue[Event] | None = None,
        publish_state_changes: bool = True,
        wait_for_state_changes: bool = True,
        force: bool = False,
        stop_timeout_sec: float | None = None,
    ) -> PluginStopOutcome:
        runtime_mutations = self._runtime_mutations
        if runtime_mutations is None:
            raise StateError(
                "Runtime mutations must be bound before use.",
                operation="orchestrator.lifecycle.shutdown.stop_plugin",
            )
        return await runtime_mutations.submit_stop_plugin(
            RuntimeMutationStopRequest(
                plugin_name=plugin_name,
                reason=reason,
                reply_channel=reply_channel,
                publish_state_changes=publish_state_changes,
                wait_for_state_changes=wait_for_state_changes,
                force=force,
                stop_timeout_sec=stop_timeout_sec,
            ),
        )

    async def execute_stop_plugin(
        self,
        request: RuntimeMutationStopRequest,
    ) -> PluginStopOutcome:
        async def _perform_stop_logic(plugin_name: str) -> PluginStopOutcome:
            return await perform_plugin_stop_logic(
                self._deps,
                self._health_check_config,
                plugin_name,
                stop_timeout_sec=request.stop_timeout_sec,
            )

        return await execute_stop_plugin_request(
            deps=self._deps,
            request=request,
            perform_plugin_stop_logic=_perform_stop_logic,
        )

    async def stop_plugin_for_shutdown(
        self,
        plugin_name: str,
        *,
        reason: str,
        stop_timeout_sec: float,
    ) -> PluginStopOutcome:
        lock_acquire_timeout_sec = min(
            float(CONTROL_TIMEOUT_SEC),
            stop_timeout_sec * SHUTDOWN_LOCK_ACQUIRE_BUDGET_FRACTION,
        )
        physical_stop_timeout_sec = stop_timeout_sec - lock_acquire_timeout_sec
        return await self.execute_stop_plugin(
            RuntimeMutationStopRequest(
                plugin_name=plugin_name,
                reason=reason,
                reply_channel=None,
                publish_state_changes=True,
                wait_for_state_changes=False,
                force=True,
                stop_timeout_sec=physical_stop_timeout_sec,
                lock_acquire_timeout_sec=lock_acquire_timeout_sec,
            ),
        )

    async def wait_for_active_tasks_to_drain(self, plugin_name: str) -> str | None:
        for _ in range(self._MAX_DRAIN_WAIT_ITERATIONS):
            if self._deps.shutdown_event.is_set():
                return "shutdown in progress"
            async with self._deps.state.plugins_context() as plugin_context:
                plugin_state = plugin_context.plugin_states.get(plugin_name)
                active_count = len(plugin_state.active_tasks) if plugin_state is not None else 0
            if active_count == 0:
                return None
            await asyncio.sleep(MODERATE_DELAY_SEC)
        return f"timed out waiting for {plugin_name} tasks to drain"

    async def perform_plugin_stop_logic(self, plugin_name: str) -> PluginStopOutcome:
        return await perform_plugin_stop_logic(
            self._deps,
            self._health_check_config,
            plugin_name,
            stop_timeout_sec=None,
        )
