"""SoAI - Orchestrator control internal protocols [backend/orchestrator/control/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.licensing.protocols import LicensingStatusProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
        ParameterManagerProtocol,
    )
    from core.orchestrator.protocols_lifecycle import (
        OrchestratorCircuitBreakersProtocol,
    )
    from core.orchestrator.protocols_scheduler import OrchestratorSchedulerProtocol
    from core.tasks.protocols import (
        TaskRegistryProtocol,
    )
    from orchestrator.control import config_management, request_routing, task_management
    from orchestrator.control.context_holder import ComponentContextHolder
    from orchestrator.control.plugin_command_dependencies import (
        OrchestratorPluginCommandDependencies,
    )
    from orchestrator.lifecycle.service_interfaces.internal_protocols import (
        OrchestratorLifecycleCoordinatorProtocol,
        OrchestratorLifecycleStartupProtocol,
    )
    from orchestrator.queueing.internal_protocols import QueueServiceView
    from orchestrator.types import OrchestratorDependencies

__all__ = (
    "InferenceAdmissionDependenciesProtocol",
    "InferenceAdmissionLifecycleProtocol",
    "LifecycleCircuitBreakerSurface",
    "OrchestratorControlInferenceAdmissionProtocol",
    "OrchestratorControlSubscriptionsProtocol",
    "OrchestratorPluginConfigReloadDepsSurface",
    "SchedulerLoopSurface",
)


class LifecycleCircuitBreakerSurface(Protocol):
    circuit_breakers: OrchestratorCircuitBreakersProtocol


class SchedulerLoopSurface(Protocol):
    async def scheduler_loop(self) -> None: ...


class OrchestratorPluginConfigReloadDepsSurface(Protocol):
    @property
    def orchestrator(self) -> OrchestratorDependencies: ...

    @property
    def lifecycle(self) -> OrchestratorLifecycleCoordinatorProtocol: ...

    @property
    def scheduler(self) -> OrchestratorSchedulerProtocol: ...


class OrchestratorControlSubscriptionsProtocol(Protocol):
    request_deps: request_routing.OrchestratorRequestRoutingDependencies
    task_deps: task_management.OrchestratorTaskManagementDependencies
    plugin_deps: OrchestratorPluginCommandDependencies
    config_deps: config_management.OrchestratorConfigManagementDependencies
    component_context_holder: ComponentContextHolder
    lifecycle: OrchestratorLifecycleCoordinatorProtocol

    async def handle_system_quiesce(self, event: Event) -> None: ...


class InferenceAdmissionDependenciesProtocol(Protocol):
    @property
    def licensing_status(self) -> LicensingStatusProtocol: ...

    @property
    def model_information_service(self) -> ModelInformationServiceProtocol: ...

    @property
    def model_resolution_service(self) -> ModelResolutionServiceProtocol: ...

    @property
    def param_manager(self) -> ParameterManagerProtocol: ...


class InferenceAdmissionLifecycleProtocol(Protocol):
    @property
    def startup(self) -> OrchestratorLifecycleStartupProtocol: ...


class OrchestratorControlInferenceAdmissionProtocol(Protocol):
    @property
    def deps(self) -> InferenceAdmissionDependenciesProtocol: ...

    @property
    def task_registry(self) -> TaskRegistryProtocol: ...

    @property
    def lifecycle(self) -> InferenceAdmissionLifecycleProtocol: ...

    @property
    def queue(self) -> QueueServiceView: ...

    @property
    def scheduler(self) -> OrchestratorSchedulerProtocol: ...

    def is_quiescent(self) -> bool: ...
