"""SoAI - Orchestrator control runtime lifecycle [backend/orchestrator/control/runtime_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.config.numeric import coerce_positive_float
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.subscriptions import subscribe_many, unsubscribe_many
from core.events.types_base import Event
from core.events.types_plugins import StopAllPluginsCommand
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.orchestrator.protocols_scheduler import OrchestratorSchedulerProtocol
from core.orchestrator.queue_decisions import QueueDecision
from core.plugins.dependencies import PluginGuardianDependencies
from core.plugins.protocols_guardian import PluginGuardianProtocol
from core.runtime.request_context import create_system_context
from core.tasks.protocols import SpawnTrackedBackgroundTaskCallable
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from orchestrator.control import config_management
from orchestrator.control.context_holder import ComponentContextHolder
from orchestrator.control.guardian_ref import GuardianRef
from orchestrator.control.invariants import orchestrator_invariant_monitor_loop
from orchestrator.control.plugin_command_dependencies import (
    OrchestratorPluginCommandDependencies,
)
from orchestrator.control.plugin_commands import handle_stop_all_plugins
from orchestrator.control.shutdown_tasks import cancel_shutdown_tasks
from orchestrator.control.stale_task_recovery import OrchestratedStaleTaskRecovery
from orchestrator.control.startup_background_tasks import start_control_background_tasks
from orchestrator.control.startup_diagnostics import log_startup_configuration
from orchestrator.control.startup_task_recovery import OrchestratedStartupTaskRecovery
from orchestrator.internal_protocols import OrchestratorActiveInferenceProtocol
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)
from orchestrator.queueing.internal_protocols import QueueServiceView
from orchestrator.types import OrchestratorDependencies

__all__ = (
    "OrchestratorRuntimeLifecycleDependencies",
    "OrchestratorRuntimeStartResult",
    "shutdown_orchestrator_runtime",
    "start_orchestrator_runtime",
)

LOGGER_NAME = "SoAI.orchestrator.control.runtime_lifecycle"
OPERATION_SHUTDOWN_ORCHESTRATOR_RUNTIME = "orchestrator.control.shutdown_runtime"


@dataclass(frozen=True, slots=True)
class OrchestratorRuntimeLifecycleDependencies:
    orchestrator: OrchestratorDependencies
    queue: QueueServiceView
    scheduler: OrchestratorSchedulerProtocol
    active_inferences: OrchestratorActiveInferenceProtocol
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    config_deps: config_management.OrchestratorConfigManagementDependencies
    plugin_deps: OrchestratorPluginCommandDependencies
    component_context_holder: ComponentContextHolder
    spawn_tracked_background_task: SpawnTrackedBackgroundTaskCallable
    startup_task_recovery: OrchestratedStartupTaskRecovery
    stale_task_recovery: OrchestratedStaleTaskRecovery
    guardian_builder: Callable[[PluginGuardianDependencies], PluginGuardianProtocol]
    decision_handler: Callable[[QueueDecision], Awaitable[None]]
    event_handlers: dict[type[Event], Callable[[Event], Awaitable[None]]]
    shutdown_event: asyncio.Event
    tasks_lock: asyncio.Lock
    background_tasks: set[asyncio.Task[None]]
    guardian_ref: GuardianRef

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorRuntimeLifecycleDependencies",
            active_inferences=self.active_inferences,
            background_tasks=self.background_tasks,
            component_context_holder=self.component_context_holder,
            config_deps=self.config_deps,
            decision_handler=self.decision_handler,
            event_handlers=self.event_handlers,
            guardian_builder=self.guardian_builder,
            guardian_ref=self.guardian_ref,
            lifecycle=self.lifecycle,
            orchestrator=self.orchestrator,
            plugin_deps=self.plugin_deps,
            queue=self.queue,
            scheduler=self.scheduler,
            shutdown_event=self.shutdown_event,
            spawn_tracked_background_task=self.spawn_tracked_background_task,
            stale_task_recovery=self.stale_task_recovery,
            startup_task_recovery=self.startup_task_recovery,
            tasks_lock=self.tasks_lock,
        )


@dataclass(frozen=True, slots=True)
class OrchestratorRuntimeStartResult:
    subscriptions_registered: bool
    planner_worker_count: int
    planner_worker_next_id: int


async def start_orchestrator_runtime(
    deps: OrchestratorRuntimeLifecycleDependencies,
    *,
    subscriptions_registered: bool,
    num_planner_workers: int,
    health_check_config: JSONDict,
    max_concurrent_plugins: int,
) -> OrchestratorRuntimeStartResult:
    logger = get_logger(LOGGER_NAME)
    startup_epoch_ms = epoch_ms()
    if not subscriptions_registered:
        subscribe_many(deps.orchestrator.bus, deps.event_handlers)
        subscriptions_registered = True
    await deps.lifecycle.runtime_mutations.start()
    await deps.orchestrator.model_services_ready_event.wait()
    recovered = await deps.startup_task_recovery.fail_startup_orphaned_tasks(
        started_at_epoch_ms=startup_epoch_ms,
    )
    if recovered > 0:
        logger.warning(
            "Recovered %d startup-orphaned orchestrated task(s) after restart.",
            recovered,
        )
    await deps.lifecycle.startup.load_virtual_models()
    await deps.lifecycle.circuit_breakers.load_circuit_breakers()
    guardian = deps.guardian_builder(
        PluginGuardianDependencies(
            orchestrator=deps.lifecycle,
            executor=deps.active_inferences,
            component_context=deps.component_context_holder.value,
        ),
    )
    deps.guardian_ref.value = guardian
    config_management.update_component_context(
        deps=deps.config_deps,
        component_context_holder=deps.component_context_holder,
        routing_config=deps.lifecycle.routing_config,
    )
    guardian.start()
    async with deps.tasks_lock:
        deps.background_tasks.clear()
    planner_worker_count, planner_worker_next_id = await start_control_background_tasks(
        spawn_tracked_background_task=deps.spawn_tracked_background_task,
        queue=deps.queue,
        scheduler=deps.scheduler,
        lifecycle=deps.lifecycle,
        decision_handler=deps.decision_handler,
        stale_task_recovery_loop=deps.stale_task_recovery.recovery_loop,
        num_planner_workers=num_planner_workers,
        config_deps=deps.config_deps,
    )
    invariant_interval_seconds = coerce_positive_float(
        health_check_config.get("INVARIANT_MONITOR_INTERVAL_SEC", 60.0),
        default=60.0,
        minimum=5.0,
    )
    _ = await deps.spawn_tracked_background_task(
        coro=orchestrator_invariant_monitor_loop(
            queue=deps.queue,
            capacity=deps.config_deps.capacity,
            active_inferences=deps.active_inferences,
            metrics=deps.orchestrator.metrics,
            shutdown_event=deps.shutdown_event,
            interval_seconds=invariant_interval_seconds,
        ),
        owner="invariant_monitor",
        name="orchestrator-invariant_monitor",
    )
    log_startup_configuration(
        logger=logger,
        health_check_config=health_check_config,
        max_concurrent_plugins=max_concurrent_plugins,
        num_planner_workers=num_planner_workers,
    )
    return OrchestratorRuntimeStartResult(
        subscriptions_registered=subscriptions_registered,
        planner_worker_count=planner_worker_count,
        planner_worker_next_id=planner_worker_next_id,
    )


async def shutdown_orchestrator_runtime(
    deps: OrchestratorRuntimeLifecycleDependencies,
    *,
    subscriptions_registered: bool,
    num_planner_workers: int,
    cancel_tasks_timeout_seconds: float,
) -> None:
    logger = get_logger(LOGGER_NAME)
    await deps.orchestrator.plugin_manager.begin_shutdown()
    guardian = deps.guardian_ref.value
    if guardian:
        await guardian.stop()
        deps.guardian_ref.value = None
    event = StopAllPluginsCommand(
        initiator="shutdown",
        context=create_system_context("shutdown"),
    )
    shutdown_error: Exception | None = None
    try:
        await deps.lifecycle.runtime_mutations.shutdown(
            timeout_seconds=cancel_tasks_timeout_seconds,
        )
        await handle_stop_all_plugins(event, deps=deps.plugin_deps)
    except RECOVERABLE_EXCEPTIONS as exception:
        shutdown_error = coerce_to_soai_error(
            exception,
            operation=OPERATION_SHUTDOWN_ORCHESTRATOR_RUNTIME,
        )
        log_exception(
            logger,
            shutdown_error,
            message="Orchestrator plugin shutdown phase failed before core cleanup.",
            operation=OPERATION_SHUTDOWN_ORCHESTRATOR_RUNTIME,
        )
    finally:
        await uncancel_then_cleanup(
            _finish_orchestrator_shutdown(
                deps=deps,
                logger=logger,
                subscriptions_registered=subscriptions_registered,
                num_planner_workers=num_planner_workers,
                cancel_tasks_timeout_seconds=cancel_tasks_timeout_seconds,
            ),
        )
    if shutdown_error is not None:
        raise shutdown_error


async def _finish_orchestrator_shutdown(
    *,
    deps: OrchestratorRuntimeLifecycleDependencies,
    logger: TraceLogger,
    subscriptions_registered: bool,
    num_planner_workers: int,
    cancel_tasks_timeout_seconds: float,
) -> None:
    await deps.scheduler.shutdown()
    deps.queue.priority.signal_shutdown(num_planner_workers)
    active_inference_tasks = await deps.active_inferences.get_active_inference_tasks()
    async with deps.tasks_lock:
        background_tasks = list(deps.background_tasks)
    await cancel_shutdown_tasks(
        logger=logger,
        background_tasks=background_tasks,
        active_inference_tasks=active_inference_tasks,
        timeout_seconds=cancel_tasks_timeout_seconds,
    )
    if subscriptions_registered:
        unsubscribe_many(deps.orchestrator.bus, deps.event_handlers)
    await deps.lifecycle.circuit_breakers.flush_dirty_breakers()
