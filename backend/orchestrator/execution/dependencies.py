"""SoAI - Dependency bundle for orchestrator execution services [backend/orchestrator/execution/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.licensing.protocols import LicensingStatusProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.models.protocols import (
    ModelInformationServiceProtocol,
)
from core.models.protocols_database import DatabaseModelsProtocol
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.state.protocols import StateAggregatorProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)
from core.tasks.task import Task
from orchestrator.execution.internal_protocols import (
    ActiveInferenceRegistryProtocol,
    DeliveryManagerProtocol,
    FailTaskCallable,
    InferencePayloadPreparerProtocol,
    OutcomeManagerProtocol,
    ResultProcessorProtocol,
)
from orchestrator.internal_protocols import (
    OrchestratorCapacityProtocol,
    TransientFailureCooldownsProtocol,
    VirtualModelHealthProtocol,
)
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)
from orchestrator.queueing.internal_protocols import QueueServiceView

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.types.json import JSONDict
    from orchestrator.execution.chat_template_role_policy import (
        ChatTemplateRolePolicyResolver,
    )

__all__ = (
    "DeliveryManagerDependencies",
    "ExecutorEngineDependencies",
    "InferencePayloadPreparerDependencies",
    "InflightCancellationManagerDependencies",
    "OutcomeManagerDependencies",
    "ResultProcessorDependencies",
)


@dataclass(frozen=True, slots=True)
class DeliveryManagerDependencies:
    queue: OrchestratorQueueProtocol
    task_registry: TaskRegistryProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DeliveryManagerDependencies",
            queue=self.queue,
            task_registry=self.task_registry,
        )


@dataclass(frozen=True, slots=True)
class InferencePayloadPreparerDependencies:
    queue: OrchestratorQueueProtocol
    model_information_service: ModelInformationServiceProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="InferencePayloadPreparerDependencies",
            model_information_service=self.model_information_service,
            queue=self.queue,
        )


@dataclass(frozen=True, slots=True)
class ResultProcessorDependencies:
    queue: OrchestratorQueueProtocol
    active_inferences: ActiveInferenceRegistryProtocol
    health_check_config: JSONDict
    metrics: MetricsManagerProtocol
    conservative_billing_threshold: float
    prompt_token_counter: PromptTokenCounter
    temp_directory: str | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ResultProcessorDependencies",
            active_inferences=self.active_inferences,
            conservative_billing_threshold=self.conservative_billing_threshold,
            health_check_config=self.health_check_config,
            metrics=self.metrics,
            prompt_token_counter=self.prompt_token_counter,
            queue=self.queue,
        )


@dataclass(frozen=True, slots=True)
class OutcomeManagerDependencies:
    queue: QueueServiceView
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    transient_failures: TransientFailureCooldownsProtocol
    virtual_model_health: VirtualModelHealthProtocol
    task_registry: TaskRegistryProtocol
    delivery: DeliveryManagerProtocol
    metrics: MetricsManagerProtocol
    model_information_service: ModelInformationServiceProtocol
    database_models: DatabaseModelsProtocol
    database_api_keys: DatabaseAPIKeysProtocol
    event_bus: EventBusProtocol
    temp_directory: str | None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OutcomeManagerDependencies",
            database_api_keys=self.database_api_keys,
            database_models=self.database_models,
            event_bus=self.event_bus,
            delivery=self.delivery,
            lifecycle=self.lifecycle,
            metrics=self.metrics,
            model_information_service=self.model_information_service,
            queue=self.queue,
            task_registry=self.task_registry,
            transient_failures=self.transient_failures,
            virtual_model_health=self.virtual_model_health,
        )


@dataclass(frozen=True, slots=True)
class ExecutorEngineDependencies:
    queue: QueueServiceView
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    capacity: OrchestratorCapacityProtocol
    task_registry: TaskRegistryProtocol
    state_aggregator: StateAggregatorProtocol
    active_inferences: ActiveInferenceRegistryProtocol
    payload_preparer: InferencePayloadPreparerProtocol
    results: ResultProcessorProtocol
    outcomes: OutcomeManagerProtocol
    metrics: MetricsManagerProtocol
    health_check_config: JSONDict
    role_policy_resolver: ChatTemplateRolePolicyResolver
    licensing_status: LicensingStatusProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ExecutorEngineDependencies",
            active_inferences=self.active_inferences,
            capacity=self.capacity,
            health_check_config=self.health_check_config,
            lifecycle=self.lifecycle,
            licensing_status=self.licensing_status,
            metrics=self.metrics,
            outcomes=self.outcomes,
            payload_preparer=self.payload_preparer,
            queue=self.queue,
            role_policy_resolver=self.role_policy_resolver,
            results=self.results,
            state_aggregator=self.state_aggregator,
            task_registry=self.task_registry,
        )


@dataclass(frozen=True, slots=True)
class InflightCancellationManagerDependencies:
    active_inferences: ActiveInferenceRegistryProtocol
    task_registry: TaskRegistryProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    cancel_task: Callable[[Task, str], Awaitable[None]]
    fail_task: FailTaskCallable

    def __post_init__(self) -> None:
        require_dependencies(
            owner="InflightCancellationManagerDependencies",
            active_inferences=self.active_inferences,
            cancel_task=self.cancel_task,
            cancellation_binder=self.cancellation_binder,
            fail_task=self.fail_task,
            finalizer_tracker=self.finalizer_tracker,
            task_registry=self.task_registry,
        )
