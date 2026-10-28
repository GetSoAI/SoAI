"""SoAI - GPU terminal ownership, commit delivery and client cancellation [backend/hardware/gpu_tuning/control_operation_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, overload

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import wait_for_task_completion
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import GPUControlInputValidationError, ValidationError
from core.hardware.gpu_control_types import GPUControlStartupResult
from core.hardware.gpu_operation_results import build_gpu_operation_error
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from hardware.gpu_tuning.control_operation_events import publish_completed_gpu_control_operation
from hardware.gpu_tuning.control_operation_finalization import (
    GPUControlFinalizationDependencies,
    GPUControlFinalizationTarget,
    GPUControlSnapshotScope,
    execute_finalized_gpu_control_worker,
)
from hardware.gpu_tuning.control_operations import (
    GPUControlOperationState,
    start_control_operation,
    wait_control_operation,
)
from hardware.gpu_tuning.control_worker_results import (
    GPU_CONTROL_WORKER_EXCEPTIONS,
    GPUControlOperationOutcome,
    failed_gpu_control_payload,
)
from hardware.gpu_tuning.mutation_leases import GPUControlMetadataScope
from hardware.gpu_tuning.service_dependencies import (
    GPUStartupAcquisitionResources,
    require_startup_acquisition_resources,
)
from hardware.gpu_tuning.startup_scope_types import GPUControlStartupScope

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.tasks.protocols import TaskCancellationBinderProtocol, TaskFinalizerTrackerProtocol
    from core.types.json import JSONDict


__all__ = (
    "GPUControlDeliveryDependencies",
    "run_finalized_gpu_control_operation",
)


OPERATION_CONTROL_TERMINAL = "hardware.gpu_tuning.control_terminal"


@dataclass(frozen=True, slots=True)
class GPUControlDeliveryDependencies:
    effects: GPUControlFinalizationDependencies
    logger: TraceLogger
    event_bus: EventBusProtocol | None
    main_loop: asyncio.AbstractEventLoop | None
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    executor: CommandExecutorProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GPUControlDeliveryDependencies",
            effects=self.effects,
            executor=self.executor,
            logger=self.logger,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
        )
        if not isinstance(self.effects, GPUControlFinalizationDependencies):
            raise ValidationError("GPU delivery requires its concrete effects authority.")


@overload
async def run_finalized_gpu_control_operation(
    state: GPUControlOperationState,
    deps: GPUControlDeliveryDependencies,
    *,
    operation_id: str,
    targets: (
        tuple[GPUControlFinalizationTarget, ...] | GPUControlMetadataScope | GPUControlSnapshotScope
    ),
    startup_resources: GPUStartupAcquisitionResources | None,
    worker: Callable[[CancellationTokenProtocol], GPUControlOperationOutcome],
) -> JSONDict: ...


@overload
async def run_finalized_gpu_control_operation(
    state: GPUControlOperationState,
    deps: GPUControlDeliveryDependencies,
    *,
    operation_id: str,
    targets: GPUControlStartupScope,
    startup_resources: GPUStartupAcquisitionResources,
    worker: Callable[[CancellationTokenProtocol], GPUControlOperationOutcome],
) -> GPUControlStartupResult: ...


async def run_finalized_gpu_control_operation(
    state: GPUControlOperationState,
    deps: GPUControlDeliveryDependencies,
    *,
    operation_id: str,
    targets: (
        tuple[GPUControlFinalizationTarget, ...]
        | GPUControlStartupScope
        | GPUControlMetadataScope
        | GPUControlSnapshotScope
    ),
    startup_resources: GPUStartupAcquisitionResources | None,
    worker: Callable[[CancellationTokenProtocol], GPUControlOperationOutcome],
) -> JSONDict | GPUControlStartupResult:
    targets = copy.deepcopy(targets)
    startup = isinstance(targets, GPUControlStartupScope)
    require_startup_acquisition_resources(
        targets if isinstance(targets, GPUControlStartupScope) else None, startup_resources
    )
    if isinstance(targets, tuple) and (
        not targets or len({target.result_key for target in targets}) != len(targets)
    ):
        raise ValidationError("GPU operation requires distinct frozen result targets.")
    detached = asyncio.Event()
    reported_worker_failures: list[Exception] = []
    owner = spawn_tracked_task(
        _run_and_deliver(
            state,
            deps,
            operation_id,
            targets,
            (
                worker
                if startup or isinstance(targets, GPUControlSnapshotScope)
                else partial(
                    execute_finalized_gpu_control_worker,
                    deps.effects,
                    worker,
                    metadata_scope=(
                        targets if isinstance(targets, GPUControlMetadataScope) else None
                    ),
                )
            ),
            startup_resources,
            reported_worker_failures,
        ),
        name=f"gpu-control-terminal:{operation_id}",
        logger=deps.logger,
        cancellation_binder=deps.cancellation_binder,
        cancellation_id=operation_id,
        owner="gpu-control-terminal",
        finalizer_tracker=deps.finalizer_tracker,
        owner_observes_result=True,
        done_callback=partial(
            _observe_terminal, deps, operation_id, detached, reported_worker_failures
        ),
    )
    try:
        return await asyncio.shield(owner)
    except asyncio.CancelledError:
        detached.set()
        _signal_client_cancellation(state, operation_id, owner)
        raise


def _signal_client_cancellation(
    state: GPUControlOperationState,
    operation_id: str,
    owner: asyncio.Task[JSONDict | GPUControlStartupResult],
) -> None:
    worker_state = state.workers.get(operation_id)
    if worker_state is None:
        if not owner.done():
            owner.cancel()
        return
    worker_state.cancellation.cancel("GPU client disconnected during the operation.")
    pending = state.pending.get(operation_id)
    if not worker_state.dispatched and pending is not None:
        pending.cancel()


async def _run_and_deliver(
    state: GPUControlOperationState,
    deps: GPUControlDeliveryDependencies,
    operation_id: str,
    targets: (
        tuple[GPUControlFinalizationTarget, ...]
        | GPUControlStartupScope
        | GPUControlMetadataScope
        | GPUControlSnapshotScope
    ),
    worker: Callable[[CancellationTokenProtocol], GPUControlOperationOutcome],
    startup_resources: GPUStartupAcquisitionResources | None,
    reported_worker_failures: list[Exception],
) -> JSONDict | GPUControlStartupResult:
    startup = isinstance(targets, GPUControlStartupScope)
    native = start_control_operation(
        state,
        operation_id=operation_id,
        targets=(
            targets
            if isinstance(
                targets, GPUControlStartupScope | GPUControlMetadataScope | GPUControlSnapshotScope
            )
            else tuple(item.target for item in targets)
        ),
        startup_resources=startup_resources,
        worker=worker,
    )
    owner_cancelled = False
    observed_failure: Exception | None = None
    try:
        await wait_control_operation(native, state=state)
    except asyncio.CancelledError:
        owner_cancelled = True
    except TaskCancelledError:
        owner_cancelled = True
    except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
        observed_failure = exception
    await wait_for_task_completion(native, retain_resources_until_complete=True)
    completion = state.consume(operation_id)
    if completion.failure is not None:
        reported_worker_failures.append(completion.failure)
    if observed_failure is not None and completion.failure is None:
        raise ValidationError(
            "GPU terminal owner discarded its worker failure."
        ) from observed_failure
    outcome = completion.outcome
    if outcome is None:
        if isinstance(completion.failure, GPUControlInputValidationError):
            raise completion.failure
        if completion.cancelled and completion.failure is None:
            raise asyncio.CancelledError()
        if startup:
            if completion.failure is not None:
                raise completion.failure
            raise ValidationError("GPU startup has no actual terminal observation.")
        return build_gpu_operation_error(
            "apply_failed", "GPU settings could not be applied safely."
        )
    payload = copy.deepcopy(outcome.payload)
    if completion.failure is not None and completion.failure is not outcome.failure:
        payload = failed_gpu_control_payload(outcome)
    publish_completed_gpu_control_operation(
        targets=targets,
        outcome=outcome,
        completion=completion,
        payload=payload,
        event_bus=deps.event_bus,
        main_loop=deps.main_loop,
        executor=deps.executor,
        cancellation_binder=deps.cancellation_binder,
        finalizer_tracker=deps.finalizer_tracker,
        logger=deps.logger,
        gpu_services=deps.effects.gpu_services,
    )
    payload.pop("committed_state_snapshots", None)
    payload.pop("startup_metadata_snapshots", None)
    if outcome.changed is None:
        payload.pop("changed", None)
    else:
        payload["changed"] = outcome.changed
    if owner_cancelled or (outcome.cancelled and completion.failure is None):
        raise asyncio.CancelledError()
    if startup:
        if completion.failure is not None and completion.failure is not outcome.failure:
            raise completion.failure
        if outcome.startup_result is None:
            raise ValidationError("GPU startup lost its actual typed terminal result.")
        return outcome.startup_result
    return payload


def _observe_terminal(
    deps: GPUControlDeliveryDependencies,
    operation_id: str,
    detached: asyncio.Event,
    reported_worker_failures: list[Exception],
    task: asyncio.Task[JSONDict | GPUControlStartupResult],
) -> None:
    if task.cancelled():
        return
    failure = task.exception()
    if isinstance(failure, TaskCancelledError) or any(
        failure is reported for reported in reported_worker_failures
    ):
        return
    if isinstance(failure, Exception):
        log_exception(
            deps.logger,
            failure,
            message="GPU terminal delivery failed.",
            operation=OPERATION_CONTROL_TERMINAL,
            details={"operation_id": operation_id, "client_detached": detached.is_set()},
        )
