"""SoAI - Owned GPU workers, canonical leases and shutdown drain [backend/hardware/gpu_tuning/control_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from functools import partial
from threading import Event
from typing import TYPE_CHECKING

from core.concurrency.cancellation import CancellationToken, TaskCancelledError
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    GPUControlInputValidationError,
    ServiceUnavailableError,
    ValidationError,
)
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.validation.strict_numbers import require_finite_float_strict, require_positive_int_strict
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_tuning.control_operation_finalization import (
    GPUControlSnapshotScope,
    resolve_gpu_control_operation_scope,
)
from hardware.gpu_tuning.control_worker_results import (
    GPUControlOperationCompletion,
    GPUControlOperationOutcome,
    GPUControlWorkerCompletion,
    GPUControlWorkerState,
    execute_control_worker,
)
from hardware.gpu_tuning.mutation_leases import (
    GPUControlMetadataScope,
    gpu_mutation_conflict_payload,
    release_gpu_control_leases,
)
from hardware.gpu_tuning.service_dependencies import (
    GPUStartupAcquisitionResources,
    require_startup_acquisition_resources,
)
from hardware.gpu_tuning.startup_scope_types import GPUControlStartupScope

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.gpu_physical_identity import GPUPhysicalDevice
    from core.hardware.protocols_activity import (
        HardwareActivityLeaseProtocol,
        HardwareActivityRegistryProtocol,
    )
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskCancellationBinderProtocol, TaskFinalizerTrackerProtocol

__all__ = (
    "GPUControlOperationDependencies",
    "GPUControlOperationState",
    "drain_control_operations",
    "start_control_operation",
    "wait_control_operation",
)


OPERATION_CONTROL_OPERATION = "hardware.gpu_tuning.control_operation"


@dataclass(frozen=True, slots=True)
class GPUControlOperationDependencies:
    activity_registry: HardwareActivityRegistryProtocol
    operation_lock: asyncio.Lock
    logger: LoggerProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    cancellation_binder: TaskCancellationBinderProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GPUControlOperationDependencies",
            activity_registry=self.activity_registry,
            operation_lock=self.operation_lock,
            logger=self.logger,
            finalizer_tracker=self.finalizer_tracker,
            cancellation_binder=self.cancellation_binder,
        )


@dataclass(slots=True)
class GPUControlOperationState:
    dependencies: GPUControlOperationDependencies
    retention_capacity: int
    accepting: bool = True
    pending: dict[str, asyncio.Task[GPUControlOperationOutcome]] = field(
        default_factory=dict[str, asyncio.Task[GPUControlOperationOutcome]]
    )
    completed: dict[str, GPUControlOperationOutcome] = field(
        default_factory=dict[str, GPUControlOperationOutcome]
    )
    failures: dict[str, Exception] = field(default_factory=dict[str, Exception])
    workers: dict[str, GPUControlWorkerState] = field(
        default_factory=dict[str, GPUControlWorkerState]
    )
    cancelled: set[str] = field(default_factory=set[str])

    def __post_init__(self) -> None:
        require_positive_int_strict(
            self.retention_capacity,
            error_message="GPU terminal retention capacity must be positive.",
        )

    def consume(self, operation_id: str) -> GPUControlOperationCompletion:
        pending = self.pending.get(operation_id)
        if pending is not None:
            if not pending.done():
                raise ValidationError("GPU running operation cannot be consumed.")
            _observe_operation(self, operation_id, pending)
        if (
            operation_id not in self.completed
            and operation_id not in self.failures
            and operation_id not in self.cancelled
        ):
            raise ValidationError("GPU terminal operation is unavailable.")
        completion = GPUControlOperationCompletion(
            self.completed.pop(operation_id, None),
            self.failures.pop(operation_id, None),
            operation_id in self.cancelled,
        )
        self.cancelled.discard(operation_id)
        return completion


def start_control_operation(
    state: GPUControlOperationState,
    *,
    operation_id: str,
    targets: (
        tuple[GPUPhysicalDevice, ...]
        | GPUControlStartupScope
        | GPUControlMetadataScope
        | GPUControlSnapshotScope
    ),
    startup_resources: GPUStartupAcquisitionResources | None,
    worker: Callable[[CancellationTokenProtocol], GPUControlOperationOutcome],
) -> asyncio.Task[GPUControlOperationOutcome]:
    require_canonical_trimmed_json_text(
        operation_id, error_message="GPU operation identifier is invalid."
    )
    if not state.accepting:
        raise ValidationError("GPU mutation admission is closed.")
    if (
        operation_id in state.pending
        or operation_id in state.completed
        or operation_id in state.failures
        or operation_id in state.cancelled
    ):
        raise ValidationError("GPU operation identifier is already owned.")
    if (
        len(set(state.pending) | set(state.completed) | set(state.failures) | state.cancelled)
        >= state.retention_capacity
    ):
        raise ServiceUnavailableError("GPU terminal finalization capacity is full.")
    device_ids, scope = resolve_gpu_control_operation_scope(targets)
    require_startup_acquisition_resources(
        scope if isinstance(scope, GPUControlStartupScope) else None, startup_resources
    )
    state.workers[operation_id] = GPUControlWorkerState(
        CancellationToken(operation_id, owner="gpu-control"), Event()
    )
    try:
        task = spawn_tracked_task(
            _execute_operation(state, operation_id, device_ids, worker, scope, startup_resources),
            name=f"gpu-control:{operation_id}",
            cancellation_binder=state.dependencies.cancellation_binder,
            cancellation_id=operation_id,
            owner="gpu-control",
            logger=state.dependencies.logger,
            finalizer_tracker=state.dependencies.finalizer_tracker,
            done_callback=partial(_observe_operation, state, operation_id),
            owner_observes_result=True,
        )
    except HANDLED_RUNTIME_EXCEPTIONS:
        state.workers.pop(operation_id)
        raise
    state.pending[operation_id] = task
    return task


async def wait_control_operation(
    task: asyncio.Task[GPUControlOperationOutcome], *, state: GPUControlOperationState
) -> GPUControlOperationOutcome:
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        for operation_id, pending in state.pending.items():
            if pending is task:
                worker_state = state.workers[operation_id]
                worker_state.cancellation.cancel("GPU client cancelled the operation.")
                if not worker_state.dispatched:
                    task.cancel()
                break
        raise


async def drain_control_operations(
    state: GPUControlOperationState, *, deadline_monotonic: float
) -> bool:
    deadline = require_finite_float_strict(
        deadline_monotonic, error_message="GPU shutdown deadline must be finite."
    )
    state.accepting = False
    tasks = tuple(state.pending.values())
    if not tasks:
        return True
    loop = asyncio.get_running_loop()
    if deadline <= loop.time():
        return all(task.done() for task in tasks)
    _, pending = await asyncio.wait(tasks, timeout=max(0.0, deadline - loop.time()))
    return not pending


async def _execute_operation(
    state: GPUControlOperationState,
    operation_id: str,
    device_ids: tuple[str, ...],
    worker: Callable[[CancellationTokenProtocol], GPUControlOperationOutcome],
    scope: GPUControlStartupScope | GPUControlMetadataScope | None = None,
    startup_resources: GPUStartupAcquisitionResources | None = None,
) -> GPUControlOperationOutcome:
    leases: list[HardwareActivityLeaseProtocol] = []
    registry = state.dependencies.activity_registry
    try:
        for device_id in sorted(device_ids):
            acquired = await registry.acquire(
                device_id=device_id,
                activity_type="mutation",
                owner_id=f"gpu-control:{operation_id}",
                conflict_reason="gpu_tuning_active",
            )
            if acquired.conflict is not None:
                outcome = GPUControlOperationOutcome(
                    gpu_mutation_conflict_payload(acquired.conflict),
                    (),
                    False,
                    False,
                    None,
                    False,
                    native_results=(),
                    preflight_rejections=(),
                    committed=(),
                    dirty_marker_receipt=None,
                    startup_result=None,
                )
                state.completed[operation_id] = outcome
                return outcome
            if acquired.lease is None:
                raise ValidationError("GPU activity acquisition returned no lease or conflict.")
            leases.append(acquired.lease)
        async with state.dependencies.operation_lock:
            worker_state = state.workers[operation_id]
            worker_state.dispatched = True
            completion: GPUControlWorkerCompletion = await run_joined_thread_call(
                execute_control_worker,
                worker,
                worker_state,
                scope,
                startup_resources,
                task_name=f"gpu-control-native:{operation_id}",
                retain_resources_until_complete=True,
                cancelled_result_cleanup=partial(_retain_worker_completion, state, operation_id),
                on_cancel=partial(_cancel_worker, worker_state),
            )
            _retain_worker_completion(state, operation_id, completion)
            if completion.failure is not None:
                raise completion.failure
            if completion.cancelled:
                raise TaskCancelledError(operation_id)
            if completion.outcome is None:
                raise ValidationError("GPU worker completion has no terminal outcome.")
            return completion.outcome
    finally:
        await release_gpu_control_leases(registry, tuple(leases))


def _cancel_worker(state: GPUControlWorkerState) -> None:
    state.cancellation.cancel("GPU owner cancelled the operation.")


def _retain_worker_completion(
    state: GPUControlOperationState, operation_id: str, completion: GPUControlWorkerCompletion
) -> None:
    if completion.outcome is not None:
        state.completed[operation_id] = replace(
            completion.outcome, payload=copy.deepcopy(completion.outcome.payload)
        )
    if completion.failure is not None:
        state.failures[operation_id] = completion.failure
    if completion.cancelled:
        state.cancelled.add(operation_id)


def _observe_operation(
    state: GPUControlOperationState,
    operation_id: str,
    task: asyncio.Task[GPUControlOperationOutcome],
) -> None:
    if state.pending.get(operation_id) is not task:
        return
    state.pending.pop(operation_id, None)
    state.workers.pop(operation_id, None)
    failure = None if task.cancelled() else task.exception()
    if task.cancelled() or isinstance(failure, TaskCancelledError):
        state.cancelled.add(operation_id)
    elif isinstance(failure, Exception):
        prior = state.failures.get(operation_id)
        state.failures[operation_id] = (
            ExceptionGroup("GPU worker and cleanup failed.", [prior, failure])
            if prior is not None and prior is not failure
            else failure
        )
    retained = state.failures.get(operation_id)
    if retained is not None and not isinstance(retained, GPUControlInputValidationError):
        log_exception(
            state.dependencies.logger,
            retained,
            message="GPU owned operation failed.",
            operation=OPERATION_CONTROL_OPERATION,
            details={"operation_id": operation_id},
        )
