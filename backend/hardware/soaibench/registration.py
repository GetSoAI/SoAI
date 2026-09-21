"""SoAI - SoAIBench worker registration [backend/hardware/soaibench/registration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.tasks.asyncio_task_spawner import create_tracked_and_track_task
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.task_cancellation import mark_task_cancellation_requested
from core.tasks.type_catalog import TASK_TYPE_HARDWARE_SOAIBENCH
from hardware.soaibench.active_runs import ActiveSoAIBenchRun
from hardware.soaibench.opencl_pool import SoAIBenchAdmissionCleanupError
from hardware.soaibench.registration_failure import (
    finish_start_registration_failed_preserving,
)
from hardware.soaibench.runtime import OWNER_TYPE
from hardware.soaibench.types import SoAIBenchRunStatus
from hardware.soaibench.worker import run_soaibench_worker

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.soaibench.dependencies import SoAIBenchServiceDependencies
    from hardware.soaibench.internal_protocols import SoAIBenchOpenCLExecutionProtocol
    from hardware.soaibench.registration_context import SoAIBenchRegistrationContext

__all__ = ("register_soaibench_worker",)

REGISTRATION_OPERATION = "hardware.soaibench.registration"


async def register_soaibench_worker(
    *,
    context: SoAIBenchRegistrationContext,
) -> None:
    native_task_created = False
    try:
        await _create_native_task(
            deps=context.deps,
            run=context.run,
            task_id=context.task_id,
            user_id=context.user_id,
        )
        native_task_created = True
        if context.stop_event.is_set():
            await mark_task_cancellation_requested(context.deps.task_registry, context.task_id)
        worker_start_event = asyncio.Event()
        _ = await create_tracked_and_track_task(
            _worker_wrapper(
                context=context,
                worker_start_event=worker_start_event,
            ),
            cancellation_binder=context.deps.cancellation_binder,
            cancellation_id=f"soaibench:{context.run_id}",
            owner=OWNER_TYPE,
            track_task=lambda task: _track_worker(
                context=context,
                worker_start_event=worker_start_event,
                task=task,
            ),
            name=f"soaibench-{context.run_id}",
            logger=context.deps.logger,
            metadata={"run_id": context.run_id, "device_id": context.device_id},
        )
    except asyncio.CancelledError as exception:
        await finish_start_registration_failed_preserving(
            context=context,
            native_task_created=native_task_created,
            primary_exception=exception,
            status=SoAIBenchRunStatus.CANCELLED,
            failure_reason=None,
            message="SoAIBench worker registration was cancelled.",
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced_exception = coerce_to_soai_error(
            exception,
            operation=REGISTRATION_OPERATION,
        )
        log_exception(
            context.deps.logger,
            coerced_exception,
            message="SoAIBench worker registration failed.",
            operation=REGISTRATION_OPERATION,
        )
        await finish_start_registration_failed_preserving(
            context=context,
            native_task_created=native_task_created,
            primary_exception=exception,
        )
        raise


async def _create_native_task(
    *,
    deps: SoAIBenchServiceDependencies,
    run: JSONDict,
    task_id: str,
    user_id: int,
) -> None:
    await create(
        deps.task_registry,
        task_type=TASK_TYPE_HARDWARE_SOAIBENCH,
        user_id=user_id,
        owner_id=str(run["device_id"]),
        owner_type=OWNER_TYPE,
        task_id=task_id,
        cancellation_id=f"soaibench:{run['run_id']!s}",
        status=TaskStatus.PENDING,
        progress_total=100,
        metadata={
            "run_id": str(run["run_id"]),
            "device_id": str(run["device_id"]),
            "profile": str(run["profile"]),
            "gpu_name": run.get("gpu_name"),
            "gpu_uuid": run.get("gpu_uuid"),
            "pci_bdf": run.get("pci_bdf"),
        },
    )


async def _worker_wrapper(
    *,
    context: SoAIBenchRegistrationContext,
    worker_start_event: asyncio.Event,
) -> None:
    retain_degraded_lease = False
    ownership_settled = False
    worker_entered = False
    active_execution: SoAIBenchOpenCLExecutionProtocol | None = None
    try:
        await worker_start_event.wait()
        await context.start_execution_event.wait()
        async with context.deps.opencl_pool.lease(context.stop_event) as opencl_pool:
            active_execution = opencl_pool
            worker_entered = True
            await run_soaibench_worker(
                database_hardware=context.deps.database_hardware,
                event_bus=context.deps.event_bus,
                logger=context.deps.logger,
                hardware_manager=context.deps.hardware_manager,
                opencl_pool=opencl_pool,
                run=context.run,
                identity=context.identity,
                task_registry=context.deps.task_registry,
                run_id=context.run_id,
                task_id=context.task_id,
                stop_event=context.stop_event,
                deferred_tool_activity=context.deferred_tool_activity,
            )
    except SoAIBenchAdmissionCleanupError as exception:
        active_execution = exception.child
        await finish_start_registration_failed_preserving(
            context=context,
            native_task_created=True,
            primary_exception=exception.cleanup_failure,
            failure_reason="opencl_child_termination_failed",
            message="SoAIBench OpenCL child termination could not be verified.",
            retain_degraded_lease=True,
        )
        ownership_settled = True
        raise exception.cleanup_failure from exception
    except asyncio.CancelledError as exception:
        if worker_entered:
            raise
        await finish_start_registration_failed_preserving(
            context=context,
            native_task_created=True,
            primary_exception=exception,
            status=SoAIBenchRunStatus.CANCELLED,
            failure_reason=None,
            message="SoAIBench was cancelled before OpenCL admission.",
        )
        ownership_settled = True
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        if worker_entered:
            raise
        await finish_start_registration_failed_preserving(
            context=context,
            native_task_created=True,
            primary_exception=exception,
            failure_reason="opencl_child_admission_failed",
            message="SoAIBench OpenCL child admission failed.",
        )
        ownership_settled = True
        raise
    finally:
        if not ownership_settled:
            retain_degraded_lease = active_execution is not None and active_execution.degraded
            context.active_runs.unbind(run_id=context.run_id, lease_id=context.lease_id)
            if retain_degraded_lease:
                await uncancel_then_cleanup(
                    context.deps.activity_registry.mark_degraded(
                        device_id=context.device_id,
                        lease_id=context.lease_id,
                        reason="SoAIBench OpenCL child exit could not be verified.",
                    ),
                )
            else:
                await uncancel_then_cleanup(
                    context.deps.activity_registry.release(
                        device_id=context.device_id,
                        lease_id=context.lease_id,
                    ),
                )


def _track_worker(
    *,
    context: SoAIBenchRegistrationContext,
    worker_start_event: asyncio.Event,
    task: asyncio.Task[None],
) -> None:
    if task.done() or task.cancelling():
        raise ValidationError("SoAIBench worker was cancelled before active tracking.")
    context.active_runs.bind_tracked_worker(
        ActiveSoAIBenchRun(
            run_id=context.run_id,
            task_id=context.task_id,
            device_id=context.device_id,
            lease_id=context.lease_id,
            stop_event=context.stop_event,
            worker=task,
        ),
    )
    worker_start_event.set()
