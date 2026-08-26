"""SoAI - Main orchestrator control and coordination service [backend/orchestrator/control/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import functools
from collections.abc import Coroutine

from core.events.types_base import Event
from core.logging.trace import get_logger
from core.orchestrator.protocols_lifecycle import (
    InferenceAdmissionReceipt,
    InferenceAdmissionRequest,
)
from core.tasks.protocols import TaskRegistryProtocol
from core.types.json import JSONDict
from orchestrator.control import config_management, request_routing, task_management
from orchestrator.control.context_holder import ComponentContextHolder
from orchestrator.control.dependencies import OrchestratorControlDependencies
from orchestrator.control.guardian_ref import GuardianRef
from orchestrator.control.inference_admission import accept_inference_request
from orchestrator.control.planner_workers import apply_planner_worker_config
from orchestrator.control.plugin_command_dependencies import (
    OrchestratorPluginCommandDependencies,
)
from orchestrator.control.runtime_lifecycle import (
    OrchestratorRuntimeLifecycleDependencies,
    shutdown_orchestrator_runtime,
    start_orchestrator_runtime,
)
from orchestrator.control.stale_task_recovery import OrchestratedStaleTaskRecovery
from orchestrator.control.startup_task_recovery import OrchestratedStartupTaskRecovery
from orchestrator.control.status import get_orchestrator_status
from orchestrator.control.subscriptions import build_orchestrator_control_event_handlers
from orchestrator.control.task_recovery_dependencies import (
    OrchestratedTaskRecoveryDependencies,
)
from orchestrator.control.tracked_task_creation import create_tracked_background_task
from orchestrator.types import OrchestratorDependencies

__all__ = ("OrchestratorControl",)

LOGGER_NAME = "SoAI.orchestrator.control.service"


class OrchestratorControl:
    _SHUTDOWN_STOP_ALL_PLUGINS_TIMEOUT_SEC = 40.0
    _SHUTDOWN_TASK_CANCEL_TIMEOUT_SEC = 20.0

    def __init__(self, deps: OrchestratorControlDependencies) -> None:
        self._subscriptions_registered = False
        self._deps = deps.orchestrator
        self._guardian_builder = deps.guardian_builder
        self._spawn_tracked_task = deps.spawn_tracked_task
        self._cancel_task = deps.cancel_task
        self.queue = deps.queue
        self.scheduler = deps.scheduler
        self.inference_executor = deps.inference_executor
        self.outcomes = deps.outcomes
        self.active_inferences = deps.active_inferences
        self.handlers = deps.handlers
        self.lifecycle = deps.lifecycle
        self.capacity = deps.capacity
        self.transient_failures = deps.transient_failures
        self.virtual_model_health = deps.virtual_model_health
        self.virtual_model_rotation = deps.virtual_model_rotation
        self._task_registry = deps.task_registry
        self._task_registry_queries = deps.task_registry_queries
        self._shutdown_event = deps.shutdown_event
        self._is_quiescent = deps.is_quiescent
        self.health_check_config = deps.config.health_check_config
        self.num_planner_workers = deps.config.num_planner_workers
        self.max_concurrent_plugins = deps.config.max_concurrent_plugins
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._tasks_lock = asyncio.Lock()
        self._planner_worker_count, self._planner_worker_next_id = 0, 0
        self.guardian_ref = GuardianRef()
        self._disabled = False
        self._state_lock = asyncio.Lock()
        self.component_context_holder: ComponentContextHolder = ComponentContextHolder()
        self.config_deps = config_management.OrchestratorConfigManagementDependencies(
            orchestrator=self._deps,
            queue=self.queue,
            scheduler=self.scheduler,
            inference_executor=self.inference_executor,
            lifecycle=self.lifecycle,
            capacity=self.capacity,
            transient_failures=self.transient_failures,
            virtual_model_health=self.virtual_model_health,
            virtual_model_rotation=self.virtual_model_rotation,
            shutdown_event=self._shutdown_event,
            guardian_ref=self.guardian_ref,
            set_health_check_config=self._set_health_check_config,
            apply_planner_worker_config=self._apply_planner_worker_config,
            set_max_concurrent_plugins=self._set_max_concurrent_plugins,
            spawn_tracked_task=deps.spawn_tracked_task,
            cancel_task=deps.cancel_task,
        )
        config_management.update_component_context(
            deps=self.config_deps,
            component_context_holder=self.component_context_holder,
            routing_config=self.lifecycle.routing_config,
        )
        self.request_deps = request_routing.OrchestratorRequestRoutingDependencies(
            queue=self.queue,
            scheduler=self.scheduler,
            outcomes=self.outcomes,
            handlers=self.handlers,
            planner=self.scheduler.planner,
            licensing_status=self._deps.licensing_status,
        )
        self.task_deps = task_management.OrchestratorTaskManagementDependencies(
            orchestrator=self._deps,
            queue=self.queue,
            active_inferences=self.active_inferences,
            outcomes=self.outcomes,
            task_registry=self._task_registry,
            task_registry_queries=self._task_registry_queries,
        )
        task_recovery_deps = OrchestratedTaskRecoveryDependencies(
            queue=self.queue,
            active_inferences=self.active_inferences,
            outcomes=self.outcomes,
            task_registry=self._task_registry,
            task_registry_queries=self._task_registry_queries,
            cancellation_history=self._deps.cancellation_history,
        )
        self.startup_task_recovery = OrchestratedStartupTaskRecovery(task_recovery_deps)
        self.stale_task_recovery = OrchestratedStaleTaskRecovery(task_recovery_deps)
        self.plugin_deps = OrchestratorPluginCommandDependencies(
            orchestrator=self._deps,
            queue=self.queue,
            scheduler=self.scheduler,
            active_inferences=self.active_inferences,
            outcomes=self.outcomes,
            lifecycle=self.lifecycle,
            task_registry=self._task_registry,
            guardian_ref=self.guardian_ref,
            spawn_background_task=self.spawn_tracked_background_task,
            shutdown_stop_all_plugins_timeout_sec=self._SHUTDOWN_STOP_ALL_PLUGINS_TIMEOUT_SEC,
        )
        self._decision_handler = functools.partial(
            request_routing.handle_queue_decision,
            self.request_deps,
        )
        self._event_handlers = build_orchestrator_control_event_handlers(self)
        self._runtime_lifecycle_deps = OrchestratorRuntimeLifecycleDependencies(
            orchestrator=self._deps,
            queue=self.queue,
            scheduler=self.scheduler,
            active_inferences=self.active_inferences,
            lifecycle=self.lifecycle,
            config_deps=self.config_deps,
            plugin_deps=self.plugin_deps,
            component_context_holder=self.component_context_holder,
            spawn_tracked_background_task=self.spawn_tracked_background_task,
            startup_task_recovery=self.startup_task_recovery,
            stale_task_recovery=self.stale_task_recovery,
            guardian_builder=self._guardian_builder,
            decision_handler=self._decision_handler,
            event_handlers=self._event_handlers,
            shutdown_event=self._shutdown_event,
            tasks_lock=self._tasks_lock,
            background_tasks=self._background_tasks,
            guardian_ref=self.guardian_ref,
        )

    def _set_health_check_config(self, config: JSONDict) -> None:
        self.health_check_config = config

    def _set_max_concurrent_plugins(self, value: int) -> None:
        self.max_concurrent_plugins = value

    def set_quiescent(self, value: bool) -> None:
        (self._is_quiescent.set if value else self._is_quiescent.clear)()

    def is_quiescent(self) -> bool:
        return self._shutdown_event.is_set() or self._is_quiescent.is_set()

    @property
    def deps(self) -> OrchestratorDependencies:
        return self._deps

    @property
    def task_registry(self) -> TaskRegistryProtocol:
        return self._task_registry

    async def spawn_tracked_background_task(
        self,
        *,
        coro: Coroutine[None, None, None],
        owner: str,
        metadata: JSONDict | None = None,
        cancellation_id: str | None = None,
        name: str | None = None,
    ) -> asyncio.Task[None]:
        task = create_tracked_background_task(
            coro=coro,
            owner=owner,
            metadata=metadata,
            cancellation_id=cancellation_id,
            name=name,
            spawn_tracked_task=self._spawn_tracked_task,
            cancellation_binder=self._deps.task_cancellation_binder,
            finalizer_tracker=self._deps.task_finalizer_tracker,
        )
        async with self._tasks_lock:
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        return task

    async def start(self) -> None:
        logger = get_logger(LOGGER_NAME)
        if self._disabled:
            logger.critical("Orchestrator is disabled and will not start.")
            return
        if self.guardian_ref.value is not None and not self._shutdown_event.is_set():
            logger.debug("Orchestrator start requested while already running; ignoring.")
            return
        if self._shutdown_event.is_set():
            self._shutdown_event.clear()
        self._is_quiescent.clear()
        logger.debug("Starting new Orchestrator...")
        start_result = await start_orchestrator_runtime(
            self._runtime_lifecycle_deps,
            subscriptions_registered=self._subscriptions_registered,
            num_planner_workers=self.num_planner_workers,
            health_check_config=self.health_check_config,
            max_concurrent_plugins=self.max_concurrent_plugins,
        )
        self._subscriptions_registered = start_result.subscriptions_registered
        self._planner_worker_count = start_result.planner_worker_count
        self._planner_worker_next_id = start_result.planner_worker_next_id

    async def _apply_planner_worker_config(self, desired_workers: int) -> None:
        async with self._state_lock:
            resolved_count, _, resolved_next_id = await apply_planner_worker_config(
                desired_workers=desired_workers,
                current_worker_count=self._planner_worker_count,
                next_worker_id=self._planner_worker_next_id,
                queue=self.queue,
                decision_handler=self._decision_handler,
                spawn_background_task=self.spawn_tracked_background_task,
            )
            self._planner_worker_count = resolved_count
            self._planner_worker_next_id = resolved_next_id
            self.num_planner_workers = resolved_count

    async def shutdown(self) -> None:
        logger = get_logger(LOGGER_NAME)
        if self._shutdown_event.is_set():
            return
        logger.debug("Orchestrator shutdown initiated.")
        self._shutdown_event.set()
        await shutdown_orchestrator_runtime(
            self._runtime_lifecycle_deps,
            subscriptions_registered=self._subscriptions_registered,
            num_planner_workers=self.num_planner_workers,
            cancel_tasks_timeout_seconds=self._SHUTDOWN_TASK_CANCEL_TIMEOUT_SEC,
        )
        self._subscriptions_registered = False
        logger.debug("Orchestrator has been shut down.")

    async def handle_system_quiesce(self, event: Event) -> None:
        logger = get_logger(LOGGER_NAME)
        del event
        self._is_quiescent.set()
        logger.debug("Orchestrator is now quiescent. No new tasks will be accepted.")

    async def get_status(self) -> JSONDict:
        return await get_orchestrator_status(
            disabled=self._disabled,
            queue=self.queue,
            lifecycle=self.lifecycle,
            active_inferences=self.active_inferences,
            capacity=self.capacity,
            virtual_model_health=self.virtual_model_health,
        )

    async def accept_inference_request(
        self,
        request: InferenceAdmissionRequest,
    ) -> InferenceAdmissionReceipt:
        return await accept_inference_request(self, request)
