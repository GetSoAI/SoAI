"""SoAI - Orchestrator execution assembly helpers [backend/app/composition/build_orchestrator_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.capacity.capacity_service import OrchestratorCapacity
from orchestrator.execution.active_inference_service import (
    ActiveInferenceService,
    ActiveInferenceServiceDependencies,
)
from orchestrator.execution.active_inferences import (
    ActiveInferenceRegistry,
    ActiveInferenceRegistryDependencies,
)
from orchestrator.execution.cancellation import InflightCancellationManager
from orchestrator.execution.chat_template_role_policy import (
    ChatTemplateRolePolicyResolver,
    ChatTemplateRolePolicyResolverDependencies,
)
from orchestrator.execution.delivery import DeliveryManager
from orchestrator.execution.dependencies import (
    DeliveryManagerDependencies,
    ExecutorEngineDependencies,
    InferencePayloadPreparerDependencies,
    InflightCancellationManagerDependencies,
    OutcomeManagerDependencies,
    ResultProcessorDependencies,
)
from orchestrator.execution.engine import ExecutorEngine
from orchestrator.execution.inference_executor import OrchestratorInferenceExecutor
from orchestrator.execution.inference_executor_dependencies import (
    OrchestratorInferenceExecutorDependencies,
)
from orchestrator.execution.outcomes import OutcomeManager
from orchestrator.execution.payload import InferencePayloadPreparer
from orchestrator.execution.results import ResultProcessor
from orchestrator.failover_cooldowns import TransientFailureCooldowns
from orchestrator.lifecycle.service import OrchestratorLifecycle
from orchestrator.queueing.service import OrchestratorQueue
from orchestrator.types import OrchestratorDependencies
from orchestrator.virtual_model_health import VirtualModelHealth

__all__ = ("build_orchestrator_execution",)


def build_orchestrator_execution(
    *,
    deps: OrchestratorDependencies,
    config: OrchestratorRuntimeConfig,
    queue: OrchestratorQueue,
    lifecycle: OrchestratorLifecycle,
    capacity: OrchestratorCapacity,
    transient_failures: TransientFailureCooldowns,
    virtual_model_health: VirtualModelHealth,
    task_registry: TaskRegistryProtocol,
    temp_directory: str | None,
) -> tuple[OrchestratorInferenceExecutor, OutcomeManager, ActiveInferenceService]:
    active_inferences = ActiveInferenceRegistry(ActiveInferenceRegistryDependencies())
    delivery = DeliveryManager(
        DeliveryManagerDependencies(
            queue=queue,
            task_registry=task_registry,
        ),
    )
    payload_preparer = InferencePayloadPreparer(
        InferencePayloadPreparerDependencies(
            queue=queue,
            model_information_service=deps.model_information_service,
        ),
    )
    results = ResultProcessor(
        ResultProcessorDependencies(
            queue=queue,
            active_inferences=active_inferences,
            health_check_config=config.health_check_config,
            metrics=deps.metrics,
            conservative_billing_threshold=config.conservative_billing_threshold,
            prompt_token_counter=deps.prompt_token_counter,
            temp_directory=temp_directory,
        ),
    )
    outcomes = OutcomeManager(
        OutcomeManagerDependencies(
            queue=queue,
            lifecycle=lifecycle,
            transient_failures=transient_failures,
            virtual_model_health=virtual_model_health,
            task_registry=task_registry,
            delivery=delivery,
            metrics=deps.metrics,
            model_information_service=deps.model_information_service,
            database_models=deps.database_models,
            database_api_keys=deps.database_api_keys,
            event_bus=deps.bus,
            temp_directory=temp_directory,
        ),
    )
    role_policy_resolver = ChatTemplateRolePolicyResolver(
        ChatTemplateRolePolicyResolverDependencies(config=deps.config),
    )
    engine = ExecutorEngine(
        ExecutorEngineDependencies(
            queue=queue,
            lifecycle=lifecycle,
            capacity=capacity,
            task_registry=task_registry,
            state_aggregator=deps.state_aggregator,
            active_inferences=active_inferences,
            payload_preparer=payload_preparer,
            results=results,
            outcomes=outcomes,
            metrics=deps.metrics,
            health_check_config=config.health_check_config,
            role_policy_resolver=role_policy_resolver,
            licensing_status=deps.licensing_status,
        ),
    )
    cancellations = InflightCancellationManager(
        InflightCancellationManagerDependencies(
            active_inferences=active_inferences,
            task_registry=task_registry,
            cancellation_binder=deps.task_cancellation_binder,
            finalizer_tracker=deps.task_finalizer_tracker,
            cancel_task=outcomes.cancel_task,
            fail_task=outcomes.fail_task,
        ),
    )
    inference_executor = OrchestratorInferenceExecutor(
        OrchestratorInferenceExecutorDependencies(
            orchestrator=deps,
            config=config,
            routing_config=deps.routing_config,
            queue=queue,
            lifecycle=lifecycle,
            task_registry=task_registry,
            active_inferences=active_inferences,
            cancellations=cancellations,
            results=results,
            engine=engine,
            outcomes=outcomes,
        ),
    )
    active_inference_service = ActiveInferenceService(
        ActiveInferenceServiceDependencies(
            active_inferences=active_inferences,
            cancellations=cancellations,
        ),
    )
    return (inference_executor, outcomes, active_inference_service)
