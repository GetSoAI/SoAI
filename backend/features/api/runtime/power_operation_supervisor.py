"""SoAI - Durable power operation lifecycle supervisor [backend/features/api/runtime/power_operation_supervisor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ServiceUnavailableError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import TraceLogger
from core.runtime.soai_identifiers import create_system_id
from core.system.power_operations import (
    PowerOperation,
    PowerOperationAction,
)
from core.system.protocols import PowerOperationRepositoryProtocol
from core.tasks.asyncio_task_spawner import create_tracked_and_track_task
from core.tasks.asyncio_task_tracking import cancel_and_await_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.timing.constants import CONTROL_TIMEOUT_SEC
from core.timing.epoch import epoch_ms
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from features.api.runtime.power_operation_dispatch import (
    PowerDispatchFailure,
    PowerOperationDispatcher,
)
from features.api.runtime.power_operation_events import PowerOperationEventPublisher

__all__ = (
    "PowerOperationSupervisor",
    "PowerOperationSupervisorDependencies",
)

_CLAIM_LEASE_MS = 30_000
_MAX_ATTEMPTS = 3
_MAX_WAIT_SECONDS = 3600.0
_OPERATION = "api_power.supervisor"


@dataclass(frozen=True, slots=True)
class PowerOperationSupervisorDependencies:
    repository: PowerOperationRepositoryProtocol
    dispatcher: PowerOperationDispatcher
    event_publisher: PowerOperationEventPublisher
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    logger: TraceLogger

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PowerOperationSupervisorDependencies",
            repository=self.repository,
            dispatcher=self.dispatcher,
            event_publisher=self.event_publisher,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            logger=self.logger,
        )


class PowerOperationSupervisor:
    def __init__(self, deps: PowerOperationSupervisorDependencies) -> None:
        self._repository = deps.repository
        self._dispatcher = deps.dispatcher
        self._event_publisher = deps.event_publisher
        self._cancellation_binder = deps.cancellation_binder
        self._finalizer_tracker = deps.finalizer_tracker
        self._logger = deps.logger
        self._claim_owner = create_system_id(
            subsystem="power_supervisor",
            owner="runtime",
            include_random_suffix=True,
        )
        self._wake_event = asyncio.Event()
        self._shutdown_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._is_ready = False

    @property
    def is_ready(self) -> bool:
        task = self._task
        return self._is_ready and task is not None and not task.done()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._shutdown_event.clear()
        try:
            await self._reconcile()
            self._is_ready = True
        except RECOVERABLE_EXCEPTIONS as exception:
            self._is_ready = False
            log_exception(
                self._logger,
                exception,
                message="Power operation startup reconciliation failed.",
                operation=_OPERATION,
                level="error",
            )
        self._task = await create_tracked_and_track_task(
            self._run(),
            cancellation_binder=self._cancellation_binder,
            cancellation_id=self._claim_owner,
            owner="power_operation_supervisor",
            name="power-operation-supervisor",
            logger=self._logger,
            track_task=self._finalizer_tracker.track_finalizer,
        )

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        self._wake_event.set()
        task = self._task
        self._is_ready = False
        try:
            if task is not None:
                try:
                    await asyncio.wait_for(
                        asyncio.shield(task),
                        timeout=CONTROL_TIMEOUT_SEC,
                    )
                except TimeoutError:
                    await cancel_and_await_tracked_task(task, logger=self._logger)
        finally:
            self._task = None

    async def accept(
        self,
        *,
        operation_id: str,
        owner_id: int,
        action: PowerOperationAction,
        force: bool,
        delay_ms: int,
    ) -> PowerOperation:
        self._require_ready()
        try:
            operation = await asyncio.wait_for(
                self._repository.accept(
                    operation_id=operation_id,
                    owner_id=owner_id,
                    action=action,
                    force=force,
                    delay_ms=delay_ms,
                    accepted_at_ms=epoch_ms(),
                ),
                timeout=CONTROL_TIMEOUT_SEC,
            )
        finally:
            self._wake_event.set()
        await self._event_publisher.publish(operation)
        return operation

    async def get(self, operation_id: str) -> PowerOperation | None:
        return await self._repository.get(operation_id)

    async def get_active(self) -> PowerOperation | None:
        return await self._repository.get_active()

    async def cancel(self, operation_id: str) -> PowerOperation:
        self._require_ready()
        operation = await self._repository.cancel(operation_id, cancelled_at_ms=epoch_ms())
        await self._event_publisher.publish(operation)
        self._wake_event.set()
        return operation

    def _require_ready(self) -> None:
        if not self.is_ready:
            raise ServiceUnavailableError("Power operation supervisor is degraded.")

    async def _run(self) -> None:
        failure_count = 0
        while not self._shutdown_event.is_set():
            try:
                await self._reconcile()
                claimed = await self._repository.claim_due(
                    now_ms=epoch_ms(),
                    claim_owner=self._claim_owner,
                    lease_duration_ms=_CLAIM_LEASE_MS,
                    max_attempts=_MAX_ATTEMPTS,
                )
                if claimed is not None:
                    self._is_ready = True
                    failure_count = 0
                    await self._execute_claimed(claimed)
                    continue
                self._is_ready = True
                failure_count = 0
                await self._wait_for_work()
            except RECOVERABLE_EXCEPTIONS as exception:
                self._is_ready = False
                log_exception(
                    self._logger,
                    exception,
                    message="Power operation supervisor iteration failed.",
                    operation=_OPERATION,
                    level="error",
                )
                delay = compute_exponential_backoff_seconds(
                    failure_count,
                    base_seconds=0.25,
                    maximum_seconds=30.0,
                    jitter_ratio=0.2,
                )
                failure_count += 1
                await self._wait(delay)

    async def _execute_claimed(self, operation: PowerOperation) -> None:
        checkpointed = await self._repository.mark_dispatch_started(
            operation.operation_id,
            claim_owner=self._claim_owner,
            dispatch_started_at_ms=epoch_ms(),
        )
        await self._event_publisher.publish(checkpointed)
        try:
            result_code = await self._dispatcher.dispatch(checkpointed)
        except PowerDispatchFailure as exception:
            details = exception.details
            error_code = details.get("error_code") if details is not None else None
            if not isinstance(error_code, str) or not error_code:
                raise StateError("Power dispatch failure omitted its error code.") from exception
            terminal = await self._repository.fail(
                checkpointed.operation_id,
                claim_owner=self._claim_owner,
                completed_at_ms=epoch_ms(),
                error_code=error_code,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Power dispatch outcome is unknown after its durable checkpoint.",
                operation=_OPERATION,
                level="error",
            )
            terminal = await self._repository.fail(
                checkpointed.operation_id,
                claim_owner=self._claim_owner,
                completed_at_ms=epoch_ms(),
                error_code="power_outcome_unknown",
            )
        else:
            terminal = await self._repository.complete(
                checkpointed.operation_id,
                claim_owner=self._claim_owner,
                completed_at_ms=epoch_ms(),
                result_code=result_code,
            )
        await self._event_publisher.publish(terminal)

    async def _reconcile(self) -> None:
        changed = await self._repository.reconcile(
            now_ms=epoch_ms(),
            max_attempts=_MAX_ATTEMPTS,
        )
        for operation in changed:
            await self._event_publisher.publish(operation)

    async def _wait_for_work(self) -> None:
        self._wake_event.clear()
        if self._shutdown_event.is_set():
            return
        next_wake_at_ms = await self._repository.next_wake_at_ms()
        if self._wake_event.is_set() or self._shutdown_event.is_set():
            return
        if next_wake_at_ms is None:
            await self._wait(_MAX_WAIT_SECONDS, clear_first=False)
            return
        delay_seconds = max(0.0, (next_wake_at_ms - epoch_ms()) / 1000.0)
        await self._wait(
            min(delay_seconds, _MAX_WAIT_SECONDS),
            clear_first=False,
        )

    async def _wait(self, timeout_seconds: float, *, clear_first: bool = True) -> None:
        if clear_first:
            self._wake_event.clear()
        try:
            await asyncio.wait_for(self._wake_event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            return
