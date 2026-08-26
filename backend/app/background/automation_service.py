"""SoAI - Automation scheduler and worker service [backend/app/background/automation_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.background.automation_cycle import (
    claim_due_automation_runs,
    load_automation_service_settings,
)
from app.background.automation_queue import AutomationRunQueue
from app.background.automation_reconciliation import (
    reconcile_automation_runs,
    reconcile_queued_automation_runs,
    reconcile_stale_running_automation_runs,
)
from app.background.automation_worker_runtime import (
    run_automation_worker_loop,
    wait_for_automation_tick,
)
from app.background.runtime_api_dependencies import resolve_api_dependencies_from_runtime
from core.concurrency.task_groups import cancel_and_await
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_webui import (
    AutomationCreatedEvent,
    AutomationDeletedEvent,
    AutomationRunCreatedEvent,
    AutomationUpdatedEvent,
)
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.tasks.progress import await_background_task_shutdown
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.tasks.supervised_task_spawner import spawn_supervised_tracked_task
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.automation.protocols_database import (
        DatabaseAutomationRunSchedulerProtocol,
        DatabaseAutomationRunsProtocol,
        DatabaseAutomationsProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.runtime.protocols import RuntimeStateStoreProtocol

    type CoroutineFactory = Callable[[], Awaitable[None]]

__all__ = (
    "AutomationService",
    "AutomationServiceDependencies",
)

LOGGER_NAME = "SoAI.app.background.automation_service"
OPERATION_APP_BACKGROUND_AUTOMATION_SERVICE_SHUTDOWN = "app.background.automation_service.shutdown"
OPERATION_APP_BACKGROUND_AUTOMATION_SERVICE_TICK = "app.background.automation_service.tick"


@dataclass(frozen=True, slots=True)
class AutomationServiceDependencies:
    config: ConfigProtocol
    database_automations: DatabaseAutomationsProtocol
    database_automation_runs: DatabaseAutomationRunsProtocol
    database_automation_run_scheduler: DatabaseAutomationRunSchedulerProtocol
    event_bus: EventBusProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    runtime_state: RuntimeStateStoreProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="AutomationServiceDependencies",
            cancellation_binder=self.cancellation_binder,
            config=self.config,
            database_automation_run_scheduler=self.database_automation_run_scheduler,
            database_automation_runs=self.database_automation_runs,
            database_automations=self.database_automations,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
            runtime_state=self.runtime_state,
        )


class AutomationService:
    def __init__(self, deps: AutomationServiceDependencies) -> None:
        self._deps = deps
        self._logger = get_logger(LOGGER_NAME)
        self._shutdown_event = asyncio.Event()
        self._wake_event = asyncio.Event()
        self._queue = AutomationRunQueue(maxsize=1)
        self._main_task: asyncio.Task[None] | None = None
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._subscribed = False

    async def _handle_schedule_event(self, event: Event) -> None:
        _ = event
        self._wake_event.set()

    async def _handle_run_created_event(self, event: Event) -> None:
        if not isinstance(event, AutomationRunCreatedEvent):
            return
        run_record = await self._deps.database_automation_runs.get_run_for_execution(event.run_id)
        if not isinstance(run_record, dict):
            return
        if run_record.get("status") != "queued":
            return
        self._queue.enqueue_run_id(event.run_id)

    def _build_scheduler_task_factory(
        self,
        *,
        tick_seconds: float,
        due_batch_limit: int,
        max_concurrent_runs_per_user: int,
    ) -> CoroutineFactory:
        async def _run_scheduler() -> None:
            await self._run_service_loop(
                tick_seconds,
                due_batch_limit,
                max_concurrent_runs_per_user,
            )

        return _run_scheduler

    def _build_worker_task_factory(self, worker_index: int) -> CoroutineFactory:
        async def _run_worker() -> None:
            await self._run_worker_loop(worker_index)

        return _run_worker

    async def start(self) -> None:
        if self._main_task is not None and (not self._main_task.done()):
            return
        settings = load_automation_service_settings(self._deps.config)
        self._shutdown_event = asyncio.Event()
        self._wake_event = asyncio.Event()
        self._queue.reset(settings.queue_size)
        self._worker_tasks = []
        if not self._subscribed:
            for event_type in (
                AutomationCreatedEvent,
                AutomationUpdatedEvent,
                AutomationDeletedEvent,
            ):
                self._deps.event_bus.subscribe(event_type, self._handle_schedule_event)
            self._deps.event_bus.subscribe(
                AutomationRunCreatedEvent,
                self._handle_run_created_event,
            )
            self._subscribed = True
        self._main_task = spawn_supervised_tracked_task(
            self._build_scheduler_task_factory(
                tick_seconds=settings.tick_seconds,
                due_batch_limit=settings.due_batch_limit,
                max_concurrent_runs_per_user=settings.max_concurrent_runs_per_user,
            ),
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            cancellation_id=build_soai_id(("sys", "automation", "scheduler")),
            owner="automation_service",
            name="automation-scheduler",
            logger=self._logger,
            metadata={
                "tick_ms": int(settings.tick_seconds * 1000.0),
                "due_batch_limit": settings.due_batch_limit,
            },
        )
        for worker_index in range(settings.max_concurrent_runs):
            self._worker_tasks.append(
                spawn_supervised_tracked_task(
                    self._build_worker_task_factory(worker_index),
                    cancellation_binder=self._deps.cancellation_binder,
                    finalizer_tracker=self._deps.finalizer_tracker,
                    cancellation_id=build_soai_id(
                        (
                            "sys",
                            "automation",
                            "worker",
                            safe_or_hashed_segment(str(worker_index)),
                        ),
                    ),
                    owner="automation_service",
                    name=f"automation-worker-{worker_index}",
                    logger=self._logger,
                    metadata={"worker_index": worker_index},
                ),
            )

    async def _run_service_loop(
        self,
        tick_seconds: float,
        due_batch_limit: int,
        max_concurrent_runs_per_user: int,
    ) -> None:
        api_dependencies = await resolve_api_dependencies_from_runtime(self._deps.runtime_state)
        scheduler = self._deps.database_automation_run_scheduler
        await reconcile_automation_runs(
            api_dependencies,
            scheduler,
            enqueue_run_id=self._queue.enqueue_run_id,
        )
        while not self._shutdown_event.is_set():
            try:
                await reconcile_stale_running_automation_runs(
                    api_dependencies,
                    scheduler,
                    now_ms=epoch_ms(),
                )
                await reconcile_queued_automation_runs(
                    scheduler,
                    enqueue_run_id=self._queue.enqueue_run_id,
                )
                await claim_due_automation_runs(
                    api_dependencies,
                    scheduler,
                    due_batch_limit=due_batch_limit,
                    max_concurrent_runs_per_user=max_concurrent_runs_per_user,
                    enqueue_run_id=self._queue.enqueue_run_id,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    self._logger,
                    exception,
                    message="Automation scheduler tick failed.",
                    operation=OPERATION_APP_BACKGROUND_AUTOMATION_SERVICE_TICK,
                    level="warning",
                )
            if not await wait_for_automation_tick(
                shutdown_event=self._shutdown_event,
                wake_event=self._wake_event,
                tick_seconds=tick_seconds,
            ):
                return

    async def _run_worker_loop(self, worker_index: int) -> None:
        await run_automation_worker_loop(
            runtime_state=self._deps.runtime_state,
            run_queue=self._queue.run_queue,
            queued_run_ids=self._queue.queued_run_ids,
            shutdown_event=self._shutdown_event,
            refill_run_queue=self._queue.refill_run_queue,
            worker_index=worker_index,
        )

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        self._wake_event.set()
        await await_background_task_shutdown(
            self._main_task,
            logger=self._logger,
            operation="app.background.automation_service.shutdown",
            message="Automation scheduler failed during shutdown (non-critical).",
            level="debug",
        )
        self._main_task = None
        await cancel_and_await(
            self._worker_tasks,
            logger=self._logger,
            task_label="automation workers",
        )
        self._worker_tasks.clear()
        self._queue.clear()
        if not self._subscribed:
            return
        self._subscribed = False
        try:
            for event_type in (
                AutomationCreatedEvent,
                AutomationUpdatedEvent,
                AutomationDeletedEvent,
            ):
                self._deps.event_bus.unsubscribe(event_type, self._handle_schedule_event)
            self._deps.event_bus.unsubscribe(
                AutomationRunCreatedEvent,
                self._handle_run_created_event,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                self._logger,
                exception,
                message="Automation service event unsubscribe failed (non-critical).",
                operation=OPERATION_APP_BACKGROUND_AUTOMATION_SERVICE_SHUTDOWN,
                level="warning",
            )
