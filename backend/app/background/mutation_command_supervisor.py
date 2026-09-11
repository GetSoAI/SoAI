"""SoAI - Durable mutation command supervisor [backend/app/background/mutation_command_supervisor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.background.mutation_claim_recovery import claim_expired_mutation_candidate
from app.background.mutation_command_execution import (
    MutationCommandExecutionDependencies,
    execute_mutation_claim,
)
from app.background.mutation_recovery_health import (
    MutationRecoveryHealthMonitor,
    MutationRecoveryHealthMonitorDependencies,
)
from core.database.mutation_requests import MutationClaim
from core.database.protocols_tasks import DatabaseTasksProtocol
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.events.types_tasks import MutationDispatchRequestedEvent
from core.logging.trace import get_logger
from core.mutations.edition_composition import DurableMutationComposition
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.runtime.soai_identifiers import create_system_id
from core.tasks.progress import await_background_task_shutdown
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)
from core.tasks.supervised_task_spawner import spawn_supervised_tracked_task
from core.timing.epoch import epoch_ms
from core.validation.strict_numbers import (
    coerce_non_negative_float_strict_or_zero,
    require_positive_int_strict,
)

__all__ = (
    "MutationCommandSupervisor",
    "MutationCommandSupervisorDependencies",
)

LOGGER_NAME = "SoAI.app.background.mutation_command_supervisor"
OPERATION = "mutation_command_supervisor.worker"


@dataclass(frozen=True, slots=True)
class MutationCommandSupervisorDependencies:
    startup_ready_event: asyncio.Event
    database_tasks: DatabaseTasksProtocol
    database_plugins: DatabasePluginsProtocol
    event_bus: EventBusProtocol
    task_registry: TaskRegistryProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    plugin_directory: str
    durable_mutations: DurableMutationComposition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MutationCommandSupervisorDependencies",
            startup_ready_event=self.startup_ready_event,
            database_tasks=self.database_tasks,
            database_plugins=self.database_plugins,
            event_bus=self.event_bus,
            task_registry=self.task_registry,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            plugin_directory=self.plugin_directory,
            durable_mutations=self.durable_mutations,
        )


class MutationCommandSupervisor:
    def __init__(
        self,
        deps: MutationCommandSupervisorDependencies,
        *,
        max_workers: int = 8,
        poll_interval_sec: float = 1.0,
        lease_duration_ms: int = 30_000,
        heartbeat_interval_sec: float = 5.0,
    ) -> None:
        try:
            validated_workers = require_positive_int_strict(
                max_workers,
                error_message="Mutation supervisor max_workers must be a positive integer.",
            )
            validated_lease_duration = require_positive_int_strict(
                lease_duration_ms,
                error_message="Mutation supervisor lease_duration_ms must be a positive integer.",
            )
        except ValidationError as exception:
            raise ValueError(exception.message) from exception
        validated_poll_interval = coerce_non_negative_float_strict_or_zero(poll_interval_sec)
        validated_heartbeat_interval = coerce_non_negative_float_strict_or_zero(
            heartbeat_interval_sec
        )
        if validated_poll_interval <= 0.0:
            raise ValueError("Mutation supervisor poll_interval_sec must be positive and finite.")
        if validated_heartbeat_interval <= 0.0:
            raise ValueError(
                "Mutation supervisor heartbeat_interval_sec must be positive and finite."
            )
        if validated_heartbeat_interval * 1000.0 >= validated_lease_duration:
            raise ValueError("Mutation supervisor heartbeat must be shorter than its lease.")
        self._deps = deps
        self._execution_deps = MutationCommandExecutionDependencies(
            database_tasks=deps.database_tasks,
            database_plugins=deps.database_plugins,
            event_bus=deps.event_bus,
            task_registry=deps.task_registry,
            durable_mutations=deps.durable_mutations,
        )
        self._max_workers = validated_workers
        self._poll_interval_sec = validated_poll_interval
        self._lease_duration_ms = validated_lease_duration
        self._heartbeat_interval_sec = validated_heartbeat_interval
        self._worker_id = create_system_id(
            subsystem="mutation_commands",
            owner="worker",
            include_random_suffix=True,
        )
        self._shutdown_event = asyncio.Event()
        self._dispatch_event = asyncio.Event()
        self._dispatch_lock = asyncio.Lock()
        self._workers: set[asyncio.Task[None]] = set()
        self._task: asyncio.Task[None] | None = None
        self._subscribed = False
        self.recovery_health = MutationRecoveryHealthMonitor(
            MutationRecoveryHealthMonitorDependencies(
                database_tasks=deps.database_tasks,
                task_registry=deps.task_registry,
            )
        )
        self._dispatch_handler: Callable[[Event], Awaitable[None]] = self._handle_dispatch_request

    async def _claim_available_mutation(self) -> MutationClaim | None:
        now_ms = epoch_ms()
        claim = await self._deps.database_tasks.claim_next_mutation(
            self._worker_id,
            now_ms=now_ms,
            lease_duration_ms=self._lease_duration_ms,
        )
        if claim is not None:
            return claim
        candidates = await self._deps.database_tasks.query_expired_mutation_recovery_candidates(
            now_ms=now_ms,
            limit=1000,
        )
        for candidate in candidates:
            claim = await claim_expired_mutation_candidate(
                self._deps.database_tasks,
                candidate,
                plugin_directory=self._deps.plugin_directory,
                worker_id=self._worker_id,
                now_ms=epoch_ms(),
                lease_duration_ms=self._lease_duration_ms,
                durable_mutations=self._deps.durable_mutations,
            )
            if claim is not None:
                return claim
        return None

    @property
    def active_workers(self) -> tuple[asyncio.Task[None], ...]:
        self._reap_workers()
        return tuple(self._workers)

    def _reap_workers(self) -> None:
        completed = {worker for worker in self._workers if worker.done()}
        self._workers.difference_update(completed)

    async def _handle_dispatch_request(self, event: Event) -> None:
        if isinstance(event, MutationDispatchRequestedEvent):
            self._dispatch_event.set()

    async def _execute_claim(self, claim: MutationClaim) -> None:
        try:
            await execute_mutation_claim(
                self._execution_deps,
                claim,
                worker_id=self._worker_id,
                lease_duration_ms=self._lease_duration_ms,
                heartbeat_interval_sec=self._heartbeat_interval_sec,
                shutdown_event=self._shutdown_event,
            )
        except SoAIError as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Durable mutation worker failed; its lease remains recoverable.",
                operation=OPERATION,
                level="error",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Durable mutation worker failed; its lease remains recoverable.",
                operation=OPERATION,
                level="error",
            )
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                coerce_to_soai_error(exception, operation=OPERATION),
                message="Unexpected durable mutation worker failure; its lease remains recoverable.",
                operation=OPERATION,
                level="error",
            )

    async def dispatch_available(self) -> int:
        started = 0
        async with self._dispatch_lock:
            self._reap_workers()
            await self.recovery_health.refresh()
            while len(self._workers) < self._max_workers and not self._shutdown_event.is_set():
                claim = await self._claim_available_mutation()
                if claim is None:
                    break
                worker = asyncio.create_task(
                    self._execute_claim(claim),
                    name=f"mutation-command-{claim.request_id}",
                )
                self._workers.add(worker)
                started += 1
        return started

    async def _run(self) -> None:
        await self._deps.startup_ready_event.wait()
        while not self._shutdown_event.is_set():
            await self.dispatch_available()
            try:
                await asyncio.wait_for(
                    self._dispatch_event.wait(),
                    timeout=self._poll_interval_sec,
                )
            except TimeoutError:
                continue
            self._dispatch_event.clear()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._shutdown_event = asyncio.Event()
        self._dispatch_event = asyncio.Event()
        if not self._subscribed:
            self._deps.event_bus.subscribe(
                MutationDispatchRequestedEvent,
                self._dispatch_handler,
            )
            self._subscribed = True
        self._task = spawn_supervised_tracked_task(
            self._run,
            name="mutation-command-supervisor",
            logger=get_logger(LOGGER_NAME),
            cancellation_binder=self._deps.cancellation_binder,
            cancellation_id=create_system_id(
                subsystem="mutation_commands",
                owner="supervisor",
                include_random_suffix=False,
            ),
            owner="mutation_command_supervisor",
            finalizer_tracker=self._deps.finalizer_tracker,
        )

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        self._dispatch_event.set()
        task = self._task
        self._task = None
        await await_background_task_shutdown(
            task,
            logger=get_logger(LOGGER_NAME),
            operation="mutation_command_supervisor.shutdown",
            message="Mutation command supervisor shutdown failed.",
            level="warning",
        )
        workers = self.active_workers
        if workers:
            worker_results = await asyncio.gather(*workers, return_exceptions=True)
            for worker_result in worker_results:
                if isinstance(worker_result, asyncio.CancelledError):
                    continue
                if isinstance(worker_result, BaseException):
                    raise worker_result
        if self._subscribed:
            self._deps.event_bus.unsubscribe(
                MutationDispatchRequestedEvent,
                self._dispatch_handler,
            )
            self._subscribed = False
