"""SoAI - Orchestrator routing config changes and remediation loops [backend/orchestrator/control/config_management.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.events.types_base import Event
from core.events.types_models_routing_events import RoutingConfigChangedEvent
from core.logging.trace import get_logger
from core.orchestrator.protocols_scheduler import OrchestratorSchedulerProtocol
from core.orchestrator.routing_config import RoutingConfig
from core.plugins.protocols_guardian import DirectorComponentContext
from core.tasks.periodic import run_periodic_task
from core.tasks.protocols import CancelTaskCallable, SpawnTrackedTaskCallable
from orchestrator.config import build_runtime_config
from orchestrator.control.context_holder import ComponentContextHolder
from orchestrator.internal_protocols import (
    GuardianRefProtocol,
    OrchestratorCapacityProtocol,
    OrchestratorInferenceExecutorProtocol,
    TransientFailureCooldownsProtocol,
    VirtualModelHealthProtocol,
    VirtualModelRotationProtocol,
)
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)
from orchestrator.queueing.internal_protocols import QueueServiceView
from orchestrator.types import OrchestratorDependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "OrchestratorConfigManagementDependencies",
    "create_component_context",
    "handle_routing_config_changed",
    "queue_monitor_loop",
    "transient_failure_cleanup_loop",
    "update_component_context",
)

LOGGER_NAME = "SoAI.orchestrator.control.config_management"


_ROUTING_CONFIG_LIMIT_RESOLUTION_CONCURRENCY: int = 8


@dataclass(frozen=True, slots=True)
class OrchestratorConfigManagementDependencies:
    orchestrator: OrchestratorDependencies
    queue: QueueServiceView
    scheduler: OrchestratorSchedulerProtocol
    inference_executor: OrchestratorInferenceExecutorProtocol
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    capacity: OrchestratorCapacityProtocol
    transient_failures: TransientFailureCooldownsProtocol
    virtual_model_health: VirtualModelHealthProtocol
    virtual_model_rotation: VirtualModelRotationProtocol
    shutdown_event: asyncio.Event
    guardian_ref: GuardianRefProtocol
    set_health_check_config: Callable[[JSONDict], None]
    apply_planner_worker_config: Callable[[int], Awaitable[None]]
    set_max_concurrent_plugins: Callable[[int], None]
    spawn_tracked_task: SpawnTrackedTaskCallable
    cancel_task: CancelTaskCallable

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorConfigManagementDependencies",
            apply_planner_worker_config=self.apply_planner_worker_config,
            cancel_task=self.cancel_task,
            capacity=self.capacity,
            guardian_ref=self.guardian_ref,
            inference_executor=self.inference_executor,
            lifecycle=self.lifecycle,
            orchestrator=self.orchestrator,
            queue=self.queue,
            scheduler=self.scheduler,
            set_health_check_config=self.set_health_check_config,
            set_max_concurrent_plugins=self.set_max_concurrent_plugins,
            shutdown_event=self.shutdown_event,
            spawn_tracked_task=self.spawn_tracked_task,
            transient_failures=self.transient_failures,
            virtual_model_health=self.virtual_model_health,
            virtual_model_rotation=self.virtual_model_rotation,
        )


def create_component_context(
    deps: OrchestratorConfigManagementDependencies,
    routing_config: RoutingConfig,
) -> DirectorComponentContext:
    return DirectorComponentContext(
        event_bus=deps.orchestrator.bus,
        plugin_manager=deps.orchestrator.plugin_manager,
        routing_config=routing_config,
        metrics_manager=deps.orchestrator.metrics,
        audit_logger=deps.orchestrator.audit_logger,
        state_aggregator=deps.orchestrator.state_aggregator,
        cancellation_binder=deps.orchestrator.task_cancellation_binder,
        finalizer_tracker=deps.orchestrator.task_finalizer_tracker,
        spawn_tracked_task=deps.spawn_tracked_task,
        cancel_task=deps.cancel_task,
    )


def update_component_context(
    *,
    deps: OrchestratorConfigManagementDependencies,
    component_context_holder: ComponentContextHolder,
    routing_config: RoutingConfig,
) -> None:
    updated_context = create_component_context(deps, routing_config)
    component_context_holder.update(updated_context)
    guardian = deps.guardian_ref.value
    if guardian:
        guardian.update_component_context(updated_context)


async def handle_routing_config_changed(
    event: Event,
    *,
    deps: OrchestratorConfigManagementDependencies,
    component_context_holder: ComponentContextHolder,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not isinstance(event, RoutingConfigChangedEvent):
        return
    logger.info("Routing configuration changed. Reloading virtual models and concurrency limits.")
    base_routing_config = (
        event.routing_config
        if isinstance(event.routing_config, RoutingConfig)
        else deps.orchestrator.routing_config_holder.base_routing_config
    )
    database_virtual_models = await deps.orchestrator.database_models.list_all_virtual_models()
    updated_config = deps.orchestrator.routing_config_holder.replace_effective_sources(
        routing_config=base_routing_config,
        database_virtual_models=database_virtual_models,
    )
    deps.queue.routing_config = updated_config
    deps.scheduler.routing_config = updated_config
    deps.inference_executor.routing_config = updated_config
    deps.lifecycle.routing_config = updated_config
    update_component_context(
        deps=deps,
        component_context_holder=component_context_holder,
        routing_config=updated_config,
    )
    await deps.orchestrator.model_information_service.model_invalidate_list_caches()
    await deps.orchestrator.model_resolution_service.model_invalidate_resolution_cache()
    runtime_config = build_runtime_config(
        routing_config=updated_config,
        metrics=deps.orchestrator.metrics,
    )
    deps.set_health_check_config(runtime_config.health_check_config)
    await deps.apply_planner_worker_config(runtime_config.num_planner_workers)
    deps.set_max_concurrent_plugins(runtime_config.max_concurrent_plugins)
    await deps.queue.update_config(runtime_config)
    deps.scheduler.update_config(runtime_config)
    deps.inference_executor.update_config(runtime_config)
    await deps.lifecycle.update_config(runtime_config)
    deps.capacity.update_config(runtime_config)
    deps.virtual_model_rotation.update_config(runtime_config)
    deps.transient_failures.update_cooldown(runtime_config.failover_cooldown)
    deps.virtual_model_health.update_cooldown(runtime_config.failover_cooldown)
    all_plugin_states = await deps.orchestrator.state_aggregator.get_all_plugin_states()
    capacity_status = await deps.capacity.get_status_snapshot()
    plugin_names = sorted(set(capacity_status.keys()) | set(all_plugin_states.keys()))
    limit_resolution_semaphore = asyncio.Semaphore(_ROUTING_CONFIG_LIMIT_RESOLUTION_CONCURRENCY)

    async def _resolve_limit(plugin_name: str) -> tuple[str, int]:
        async with limit_resolution_semaphore:
            limit = await deps.scheduler.capacity_service.get_concurrency_limit_for_plugin(
                plugin_name=plugin_name,
            )
        return (plugin_name, limit)

    limit_resolution_tasks = [_resolve_limit(plugin_name) for plugin_name in plugin_names]
    resolved_limits = await asyncio.gather(*limit_resolution_tasks, return_exceptions=False)
    limits = dict(resolved_limits)
    plugin_count = max(len(plugin_names), 1)
    await deps.capacity.update_concurrency_limits(
        limits=limits,
        plugin_count=plugin_count,
    )
    await deps.lifecycle.startup.load_virtual_models()
    guardian = deps.guardian_ref.value
    if guardian:
        guardian.refresh_config(
            updated_config,
            component_context=component_context_holder.value,
        )


async def transient_failure_cleanup_loop(
    deps: OrchestratorConfigManagementDependencies,
) -> None:
    logger = get_logger(LOGGER_NAME)

    async def _cleanup() -> None:
        deps.transient_failures.cleanup(logger)

    await run_periodic_task(
        deps.shutdown_event,
        60,
        _cleanup,
        logger=logger,
        task_name="transient_failure_cleanup",
    )


async def queue_monitor_loop(deps: OrchestratorConfigManagementDependencies) -> None:
    logger = get_logger(LOGGER_NAME)

    async def _monitor() -> None:
        logger = get_logger(LOGGER_NAME)
        backlog_size = await deps.queue.get_total_backlog_size()
        if backlog_size > 0:
            logger.debug(
                "Orchestrator queue size: %s task(s) pending processing.",
                backlog_size,
            )

    await run_periodic_task(
        deps.shutdown_event,
        60,
        _monitor,
        logger=logger,
        task_name="queue_monitor",
    )
