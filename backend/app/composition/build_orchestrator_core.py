"""SoAI - Orchestrator core assembly helpers [backend/app/composition/build_orchestrator_core.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.composition.orchestrator_core_components import OrchestratorCoreComponents
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.capacity.capacity_service import OrchestratorCapacity
from orchestrator.capacity.dependencies import OrchestratorCapacityDependencies
from orchestrator.config import build_runtime_config
from orchestrator.failover_cooldowns import TransientFailureCooldowns
from orchestrator.lifecycle.dependencies import OrchestratorLifecycleDependencies
from orchestrator.lifecycle.service import OrchestratorLifecycle
from orchestrator.lifecycle.state_accessor import LifecycleStateAccessor
from orchestrator.queueing.cycles import (
    QueueCycleManager,
    QueueCycleManagerDependencies,
)
from orchestrator.queueing.dependencies import OrchestratorQueueDependencies
from orchestrator.queueing.scheduling_clock import (
    QueueSchedulingClock,
    QueueSchedulingClockDependencies,
)
from orchestrator.queueing.service import OrchestratorQueue
from orchestrator.types import OrchestratorDependencies
from orchestrator.virtual_model_health import VirtualModelHealth
from orchestrator.virtual_model_rotation import (
    VirtualModelRotation,
    VirtualModelRotationDependencies,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("build_orchestrator_core",)


def build_orchestrator_core(
    *,
    deps: OrchestratorDependencies,
    task_registry: TaskRegistryProtocol,
    tool_name_extractor: Callable[[list[JSONValue]], list[str]],
) -> OrchestratorCoreComponents:
    config = build_runtime_config(deps.routing_config, deps.metrics)
    shutdown_event = asyncio.Event()
    is_quiescent = asyncio.Event()
    cycles = QueueCycleManager(QueueCycleManagerDependencies(metrics=deps.metrics))
    capacity = OrchestratorCapacity(
        OrchestratorCapacityDependencies(
            config=config,
            metrics=deps.metrics,
            cycles=cycles,
        ),
    )
    transient_failures = TransientFailureCooldowns(config.failover_cooldown)
    virtual_model_health = VirtualModelHealth(config.failover_cooldown)
    virtual_model_rotation = VirtualModelRotation(
        VirtualModelRotationDependencies(config=config),
    )
    scheduling_clock = QueueSchedulingClock(
        QueueSchedulingClockDependencies(database_tasks=task_registry.database_tasks),
    )
    queue = OrchestratorQueue(
        OrchestratorQueueDependencies(
            orchestrator=deps,
            config=config,
            routing_config=deps.routing_config,
            cycles=cycles,
            task_registry=task_registry,
            scheduling_clock=scheduling_clock,
            shutdown_event=shutdown_event,
            is_quiescent=is_quiescent,
        ),
    )
    lifecycle = OrchestratorLifecycle(
        OrchestratorLifecycleDependencies(
            orchestrator=deps,
            config=config,
            routing_config=deps.routing_config,
            capacity=capacity,
            virtual_model_health=virtual_model_health,
            virtual_model_rotation=virtual_model_rotation,
            task_registry=task_registry,
            shutdown_event=shutdown_event,
            tool_name_extractor=tool_name_extractor,
            state_accessor=LifecycleStateAccessor(),
            authoritative_plugin_state_transitions=deps.authoritative_plugin_state_transitions,
        ),
    )
    return OrchestratorCoreComponents(
        config=config,
        shutdown_event=shutdown_event,
        is_quiescent=is_quiescent,
        capacity=capacity,
        transient_failures=transient_failures,
        virtual_model_health=virtual_model_health,
        virtual_model_rotation=virtual_model_rotation,
        queue=queue,
        lifecycle=lifecycle,
    )
