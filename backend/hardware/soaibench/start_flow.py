"""SoAI - SoAIBench run start flow [backend/hardware/soaibench/start_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import ConflictError, ServiceUnavailableError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_control_types import GPURecoveryAdmission, GPURecoveryAdmissionState
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.hardware.soaibench_persistence import task_id_for_run
from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallActivity
from hardware.activity_leases import lease_conflict_payload
from hardware.control_snapshots import find_gpu_entry
from hardware.gpu_inventory.identity import snapshot_gpu_entries
from hardware.gpu_inventory.physical_binding import resolve_gpu_physical_binding
from hardware.soaibench.active_runs import ActiveSoAIBenchRun, ActiveSoAIBenchRuns
from hardware.soaibench.deferred_tool_activity import (
    mark_soaibench_deferred_tool_activity_accepted,
)
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.events import publish_soaibench_run_update
from hardware.soaibench.gpu_identity import resolve_gpu_identity
from hardware.soaibench.registration import register_soaibench_worker
from hardware.soaibench.registration_context import SoAIBenchRegistrationContext
from hardware.soaibench.responses import run_response
from hardware.soaibench.start_cleanup import (
    bind_run_id_or_finish_failed,
    cleanup_cancelled_start,
    cleanup_failed_start,
    release_start_lease_preserving,
)
from hardware.soaibench.start_state import create_initial_run
from hardware.soaibench.types import (
    SoAIBenchBenchmarkMode,
    SoAIBenchProfile,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.soaibench.dependencies import SoAIBenchServiceDependencies

__all__ = ("start_soaibench_run",)

START_FLOW_OPERATION = "hardware.soaibench.start_flow"


async def start_soaibench_run(
    *,
    deps: SoAIBenchServiceDependencies,
    active_runs: ActiveSoAIBenchRuns,
    device_id: str,
    profile: SoAIBenchProfile,
    benchmark_mode: SoAIBenchBenchmarkMode,
    created_by_user_id: int,
    created_by_tool: str,
    temperature_limit_celsius: float | None,
    deferred_tool_activity: DeferredToolCallActivity | None,
) -> JSONDict:
    gpu_snapshot = await deps.hardware_manager.get_system_info(
        ["os", "cpus", "memory", "gpu"], cache=False
    )
    try:
        identity = resolve_gpu_identity(gpu_snapshot, device_id)
        selected = find_gpu_entry(gpu_snapshot, device_id)
        if selected is None:
            raise ValidationError("GPU inventory identity is unavailable.")
        if selected.get("control_binding_state") in (
            GPUPhysicalBindingState.IDENTITY_CONFLICT,
            GPUPhysicalBindingState.INVALID_RESPONSE,
        ):
            raise ValidationError("GPU inventory already records a physical identity conflict.")
        binding = resolve_gpu_physical_binding(selected, snapshot_gpu_entries(gpu_snapshot))
        if binding.state != GPUPhysicalBindingState.BOUND or binding.device is None:
            raise ValidationError("GPU inventory physical identity is unavailable or conflicting.")
    except ValidationError as exception:
        raise SoAIBenchUnsupported(
            reason="gpu_inventory_unavailable",
            message="Refresh GPU inventory before starting SoAI Bench.",
        ) from exception
    target = binding.device
    device_id = target.device_id
    await deps.opencl_pool.reconcile_retained()
    acquire = await deps.activity_registry.acquire(
        device_id=device_id,
        activity_type=f"soaibench_{profile.value}",
        owner_id=str(created_by_user_id),
        conflict_reason=_conflict_reason(profile),
    )
    if acquire.conflict is not None:
        return lease_conflict_payload(acquire.conflict)
    if acquire.lease is None:
        raise SoAIBenchUnsupported(
            reason="opencl_runtime_error",
            message="SoAI Bench activity lease acquisition failed.",
        )
    run_id = uuid.uuid4().hex
    lease_id = acquire.lease.lease_id
    task_id = task_id_for_run(run_id)
    stop_event = asyncio.Event()
    start_execution_event = asyncio.Event()
    try:
        active_runs.bind_pending(
            ActiveSoAIBenchRun(
                run_id=run_id,
                task_id=task_id,
                device_id=device_id,
                lease_id=lease_id,
                stop_event=stop_event,
            ),
        )
    except ValidationError as exception:
        await release_start_lease_preserving(
            deps=deps,
            device_id=device_id,
            lease_id=lease_id,
            primary_exception=exception,
        )
        raise
    run: JSONDict | None = None
    worker_registered = False
    try:
        try:
            admission = await run_joined_thread_call(
                partial(deps.recovery_admission.inspect, target),
                task_name=f"soaibench-{run_id}:recovery-admission",
                retain_resources_until_complete=True,
            )
            if not isinstance(admission, GPURecoveryAdmission) or not isinstance(
                admission.state, GPURecoveryAdmissionState
            ):
                raise ValidationError("GPU recovery admission returned invalid typed evidence.")
        except asyncio.CancelledError as exception:
            await cleanup_cancelled_start(
                deps=deps,
                run=None,
                device_id=device_id,
                lease_id=lease_id,
                primary_exception=exception,
            )
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            await cleanup_failed_start(
                deps=deps,
                run=None,
                device_id=device_id,
                lease_id=lease_id,
                reason="recovery_admission_failed",
                operation=START_FLOW_OPERATION,
                log_message="SoAI Bench recovery admission failed.",
                primary_exception=exception,
            )
            raise
        if admission.state != GPURecoveryAdmissionState.CLEAR:
            rejection = (
                ServiceUnavailableError(
                    "GPU recovery state is unavailable. Retry after recovery is available.",
                    operation=START_FLOW_OPERATION,
                )
                if admission.state == GPURecoveryAdmissionState.STORE_UNAVAILABLE
                else ConflictError(
                    "GPU recovery must complete before benchmarking this device.",
                    operation=START_FLOW_OPERATION,
                    details={"recovery_state": admission.state.value},
                )
            )
            await release_start_lease_preserving(
                deps=deps,
                device_id=device_id,
                lease_id=lease_id,
                primary_exception=rejection,
            )
            raise rejection
        try:
            run = await create_initial_run(
                deps=deps,
                gpu_snapshot=gpu_snapshot,
                identity=identity,
                run_id=run_id,
                device_id=device_id,
                profile=profile,
                benchmark_mode=benchmark_mode,
                user_id=created_by_user_id,
                created_by_tool=created_by_tool,
                temperature_limit_celsius=temperature_limit_celsius,
            )
            await publish_soaibench_run_update(
                event_bus=deps.event_bus,
                logger=deps.logger,
                run=run,
                update_type="created",
            )
        except SoAIBenchUnsupported as exception:
            await release_start_lease_preserving(
                deps=deps,
                device_id=device_id,
                lease_id=lease_id,
                primary_exception=exception,
            )
            raise
        except asyncio.CancelledError as exception:
            await cleanup_cancelled_start(
                deps=deps,
                run=run,
                device_id=device_id,
                lease_id=lease_id,
                primary_exception=exception,
            )
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            await cleanup_failed_start(
                deps=deps,
                run=run,
                device_id=device_id,
                lease_id=lease_id,
                reason="start_initialization_failed",
                operation=START_FLOW_OPERATION,
                log_message="SoAI Bench start failed before worker registration.",
                primary_exception=exception,
            )
            raise
        response_run = dict(run)
        response_run["task_id"] = task_id
        accepted_response = run_response(response_run, accepted=True)
        await bind_run_id_or_finish_failed(
            deps=deps,
            run=run,
            device_id=device_id,
            lease_id=lease_id,
            run_id=run_id,
        )
        deferred_response = await _mark_deferred_accepted_or_cleanup(
            deps=deps,
            deferred_tool_activity=deferred_tool_activity,
            accepted_response=accepted_response,
            task_id=task_id,
            run=run,
            device_id=device_id,
            lease_id=lease_id,
        )
        await register_soaibench_worker(
            context=SoAIBenchRegistrationContext(
                deps=deps,
                active_runs=active_runs,
                run=run,
                identity=identity,
                run_id=run_id,
                task_id=task_id,
                device_id=device_id,
                lease_id=lease_id,
                user_id=created_by_user_id,
                stop_event=stop_event,
                start_execution_event=start_execution_event,
                deferred_tool_activity=deferred_tool_activity,
            ),
        )
        worker_registered = True
        start_execution_event.set()
        return deferred_response if deferred_response is not None else accepted_response
    finally:
        if not worker_registered:
            active_runs.unbind(run_id=run_id, lease_id=lease_id)


async def _mark_deferred_accepted_or_cleanup(
    *,
    deps: SoAIBenchServiceDependencies,
    deferred_tool_activity: DeferredToolCallActivity | None,
    accepted_response: JSONDict,
    task_id: str,
    run: JSONDict,
    device_id: str,
    lease_id: str,
) -> JSONDict | None:
    if deferred_tool_activity is None:
        return None
    try:
        return await mark_soaibench_deferred_tool_activity_accepted(
            deferred_tool_activity,
            owner_task_id=task_id,
            accepted_result=accepted_response,
        )
    except asyncio.CancelledError as exception:
        await cleanup_cancelled_start(
            deps=deps,
            run=run,
            device_id=device_id,
            lease_id=lease_id,
            primary_exception=exception,
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        await cleanup_failed_start(
            deps=deps,
            run=run,
            device_id=device_id,
            lease_id=lease_id,
            reason="deferred_tool_activity_acceptance_failed",
            operation=START_FLOW_OPERATION,
            log_message="SoAI Bench deferred tool activity acceptance failed.",
            primary_exception=exception,
        )
        raise


def _conflict_reason(profile: SoAIBenchProfile) -> str:
    if profile == SoAIBenchProfile.STANDARD:
        return "duplicate_standard_benchmark"
    return "duplicate_stress_benchmark"
