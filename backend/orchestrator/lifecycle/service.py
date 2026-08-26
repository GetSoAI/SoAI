"""SoAI - Orchestrator lifecycle subsystem coordinator and dependency wiring [backend/orchestrator/lifecycle/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.orchestrator.protocols_lifecycle import (
    OrchestratorCircuitBreakersProtocol,
    OrchestratorLifecyclePublisherProtocol,
)
from core.orchestrator.routing_config import RoutingConfig, require_routing_config
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from orchestrator.lifecycle.dependencies import OrchestratorLifecycleDependencies
from orchestrator.lifecycle.model_loading import OrchestratorLifecycleModelLoading
from orchestrator.lifecycle.model_loading_dependencies import (
    OrchestratorLifecycleModelLoadingDependencies,
)
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleModelLoadingProtocol,
    OrchestratorLifecycleRecoveryProtocol,
    OrchestratorLifecycleRoutingConfigProtocol,
    OrchestratorLifecycleRuntimeMutationsProtocol,
    OrchestratorLifecycleShutdownCoordinatorProtocol,
    OrchestratorLifecycleStartupProtocol,
    OrchestratorLifecycleTaskTrackingProtocol,
    OrchestratorLifecycleUserCommandsProtocol,
    OrchestratorLifecycleWatchersProtocol,
)
from orchestrator.lifecycle.service_wiring import build_lifecycle_service_bundle

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("OrchestratorLifecycle",)


class OrchestratorLifecycle:
    def __init__(self, deps: OrchestratorLifecycleDependencies) -> None:
        self._routing_config: RoutingConfig | None = deps.routing_config
        self._shutdown_event = deps.shutdown_event
        self._task_registry = deps.task_registry
        self._tool_name_extractor = deps.tool_name_extractor

        self.capacity = deps.capacity

        self.health_check_config = deps.config.health_check_config
        self.max_recovery_attempts = deps.config.max_recovery_attempts
        self._service_bundle = build_lifecycle_service_bundle(
            deps=deps,
            routing_config_provider=self,
            task_registry=self._task_registry,
            tool_name_extractor=self._tool_name_extractor,
            shutdown_event=self._shutdown_event,
            health_check_config=self._require_health_check_config(self.health_check_config),
            max_recovery_attempts=self.max_recovery_attempts,
        )
        self.routing: OrchestratorLifecycleRoutingConfigProtocol = self._service_bundle.routing
        self.circuit_breakers: OrchestratorCircuitBreakersProtocol = (
            self._service_bundle.circuit_breakers
        )
        self.watchers: OrchestratorLifecycleWatchersProtocol = self._service_bundle.watchers
        self.publisher: OrchestratorLifecyclePublisherProtocol = self._service_bundle.publisher
        self.shutdown: OrchestratorLifecycleShutdownCoordinatorProtocol = (
            self._service_bundle.shutdown
        )
        self.task_tracking: OrchestratorLifecycleTaskTrackingProtocol = (
            self._service_bundle.task_tracking
        )
        self.runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol = (
            self._service_bundle.runtime_mutations
        )
        self.startup: OrchestratorLifecycleStartupProtocol = self._service_bundle.startup
        self.user_commands: OrchestratorLifecycleUserCommandsProtocol = (
            self._service_bundle.user_commands
        )
        self.recovery: OrchestratorLifecycleRecoveryProtocol = self._service_bundle.recovery
        self.model_loading: OrchestratorLifecycleModelLoadingProtocol = (
            OrchestratorLifecycleModelLoading(
                OrchestratorLifecycleModelLoadingDependencies(
                    orchestrator=deps.orchestrator,
                    shutdown_event=self._shutdown_event,
                    state=deps.state_accessor,
                    lifecycle_publisher=self.publisher,
                    circuit_breakers=self.circuit_breakers,
                    health_check_config=self._require_health_check_config(self.health_check_config),
                ),
            )
        )

    async def update_config(self, config: OrchestratorRuntimeConfig) -> None:
        self.health_check_config = config.health_check_config
        self.max_recovery_attempts = config.max_recovery_attempts
        await self.circuit_breakers.update_config(config)
        self.shutdown.update_config(config)
        self.model_loading.update_config(
            self._require_health_check_config(self.health_check_config),
        )
        self.recovery.update_config(self.max_recovery_attempts)

    @staticmethod
    def _require_health_check_config(value: JSONValue) -> JSONDict:
        if not isinstance(value, dict):
            raise ValidationError("Health check config must be a mapping.")
        return value

    @property
    def routing_config(self) -> RoutingConfig:
        return require_routing_config(self._routing_config)

    @routing_config.setter
    def routing_config(self, value: RoutingConfig) -> None:
        self._routing_config = value
