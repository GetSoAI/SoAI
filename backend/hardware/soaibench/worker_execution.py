"""SoAI - SoAIBench worker OpenCL execution [backend/hardware/soaibench/worker_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.serialization.json import serialize_json_compact_stable
from core.tasks.enums import TaskStatus
from core.tasks.status_transitions import update_progress
from core.timing.epoch import epoch_ms
from hardware.soaibench.events import publish_soaibench_worker_update
from hardware.soaibench.phase_telemetry import run_phase_with_telemetry
from hardware.soaibench.telemetry import SoAIBenchTelemetryAccumulator
from hardware.soaibench.types import SoAIBenchProfile, SoAIBenchRunStatus
from hardware.soaibench.worker_runtime_conditions import (
    finish_cancelled_runtime_profile,
)
from hardware.soaibench.worker_terminal import finish_success
from hardware.soaibench.workload import (
    SoAIBenchWorkloadResult,
    execute_soaibench_alu_phase,
    execute_soaibench_compute_phase,
    execute_soaibench_latency_phase,
    execute_soaibench_matrix_phase,
    execute_soaibench_memory_phase,
    execute_soaibench_mixed_phase,
    score_stress_phase,
)

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from hardware.soaibench.types import SoAIBenchGpuIdentity
    from hardware.soaibench.worker_context import (
        SoAIBenchWorkerEventContext,
        SoAIBenchWorkerRuntimeContext,
    )
    from hardware.soaibench.workload_common import SoAIBenchPhaseResult

__all__ = (
    "run_alu_phase",
    "run_compute_phase",
    "run_latency_phase",
    "run_matrix_phase",
    "run_memory_phase",
    "run_mixed_phase",
    "run_stress",
)

STRESS_SLICE_TIMEOUT_SECONDS = 45.0
STRESS_TELEMETRY_SAMPLE_INTERVAL_SECONDS = 0.1


async def run_stress(
    *,
    opencl_pool: BoundedBlockingPool,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    event_context: SoAIBenchWorkerEventContext,
    max_duration_seconds: float | None,
) -> None:
    sample_count = 0
    latest_result: SoAIBenchWorkloadResult | None = None
    latest_summary = runtime_context.base_summary
    telemetry_accumulator = SoAIBenchTelemetryAccumulator()
    started_at_monotonic = time.monotonic()
    while not runtime_context.stop_event.is_set() and not _stress_duration_elapsed(
        started_at_monotonic,
        max_duration_seconds,
    ):
        phase_run = await run_phase_with_telemetry(
            awaitable=run_mixed_phase(
                opencl_pool=opencl_pool,
                identity=runtime_context.identity,
                stress=True,
                timeout_sec=STRESS_SLICE_TIMEOUT_SECONDS,
            ),
            task_name="soaibench-stress-mixed-slice",
            runtime_context=runtime_context,
            telemetry_accumulator=telemetry_accumulator,
            sample_interval_seconds=STRESS_TELEMETRY_SAMPLE_INTERVAL_SECONDS,
        )
        latest_result = score_stress_phase(phase_run.phase_result)
        sample_count += latest_result.sample_count
        telemetry_summary = telemetry_accumulator.summary()
        summary = {
            **runtime_context.base_summary,
            **latest_result.summary,
            **telemetry_summary,
            "stress_sample_count": sample_count,
        }
        if (
            phase_run.terminal_telemetry is not None
            and not phase_run.terminal_telemetry.temperature_available
        ):
            summary["temperature_warning"] = "temperature_telemetry_unavailable"
        latest_summary = summary
        if (
            phase_run.terminal_telemetry is not None
            and phase_run.terminal_telemetry.temperature_exceeded
        ):
            await finish_success(
                database_hardware=runtime_context.database_hardware,
                task_registry=runtime_context.task_registry,
                run_id=runtime_context.run_id,
                task_id=runtime_context.task_id,
                status=SoAIBenchRunStatus.UNSTABLE,
                task_status=TaskStatus.FAILED,
                started_at_ms=runtime_context.started_at_ms,
                base_summary={
                    **summary,
                    "message": phase_run.terminal_telemetry.instability_message,
                },
                result=latest_result,
                sample_count=sample_count,
                failure_reason=phase_run.terminal_telemetry.instability_reason,
            )
            await publish_soaibench_worker_update(event_context, "terminal")
            return
        await runtime_context.database_hardware.update_soaibench_heartbeat(
            run_id=runtime_context.run_id,
            last_heartbeat_at_ms=epoch_ms(),
            sample_count=sample_count,
            summary_json=serialize_json_compact_stable(summary),
        )
        await publish_soaibench_worker_update(event_context, "heartbeat")
        await update_progress(
            runtime_context.task_registry,
            runtime_context.task_id,
            min(95, 10 + sample_count),
            status_message="SoAIBench stress slice completed.",
        )
    if latest_result is None:
        await finish_cancelled_runtime_profile(
            runtime_context=runtime_context,
            profile=SoAIBenchProfile.STRESS,
        )
        await publish_soaibench_worker_update(event_context, "terminal")
        return
    stopped_by_user = runtime_context.stop_event.is_set()
    await finish_success(
        database_hardware=runtime_context.database_hardware,
        task_registry=runtime_context.task_registry,
        run_id=runtime_context.run_id,
        task_id=runtime_context.task_id,
        status=SoAIBenchRunStatus.STOPPED if stopped_by_user else SoAIBenchRunStatus.COMPLETED,
        task_status=TaskStatus.CANCELLED if stopped_by_user else TaskStatus.COMPLETED,
        started_at_ms=runtime_context.started_at_ms,
        base_summary=latest_summary,
        result=latest_result,
        sample_count=sample_count,
    )
    await publish_soaibench_worker_update(event_context, "terminal")


def _stress_duration_elapsed(
    started_at_monotonic: float,
    max_duration_seconds: float | None,
) -> bool:
    if max_duration_seconds is None:
        return False
    return time.monotonic() - started_at_monotonic >= max_duration_seconds


async def run_compute_phase(
    *,
    opencl_pool: BoundedBlockingPool,
    identity: SoAIBenchGpuIdentity,
    timeout_sec: float,
) -> SoAIBenchPhaseResult:
    return await run_bounded_blocking_call(
        opencl_pool,
        execute_soaibench_compute_phase,
        identity,
        timeout_sec=timeout_sec,
    )


async def run_alu_phase(
    *,
    opencl_pool: BoundedBlockingPool,
    identity: SoAIBenchGpuIdentity,
    timeout_sec: float,
) -> SoAIBenchPhaseResult:
    return await run_bounded_blocking_call(
        opencl_pool,
        execute_soaibench_alu_phase,
        identity,
        timeout_sec=timeout_sec,
    )


async def run_memory_phase(
    *,
    opencl_pool: BoundedBlockingPool,
    identity: SoAIBenchGpuIdentity,
    timeout_sec: float,
) -> SoAIBenchPhaseResult:
    return await run_bounded_blocking_call(
        opencl_pool,
        execute_soaibench_memory_phase,
        identity,
        timeout_sec=timeout_sec,
    )


async def run_latency_phase(
    *,
    opencl_pool: BoundedBlockingPool,
    identity: SoAIBenchGpuIdentity,
    timeout_sec: float,
) -> SoAIBenchPhaseResult:
    return await run_bounded_blocking_call(
        opencl_pool,
        execute_soaibench_latency_phase,
        identity,
        timeout_sec=timeout_sec,
    )


async def run_matrix_phase(
    *,
    opencl_pool: BoundedBlockingPool,
    identity: SoAIBenchGpuIdentity,
    timeout_sec: float,
) -> SoAIBenchPhaseResult:
    return await run_bounded_blocking_call(
        opencl_pool,
        execute_soaibench_matrix_phase,
        identity,
        timeout_sec=timeout_sec,
    )


async def run_mixed_phase(
    *,
    opencl_pool: BoundedBlockingPool,
    identity: SoAIBenchGpuIdentity,
    stress: bool,
    timeout_sec: float,
) -> SoAIBenchPhaseResult:
    return await run_bounded_blocking_call(
        opencl_pool,
        execute_soaibench_mixed_phase,
        identity,
        stress,
        timeout_sec=timeout_sec,
    )
