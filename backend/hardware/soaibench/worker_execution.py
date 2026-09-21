"""SoAI - SoAIBench worker OpenCL execution [backend/hardware/soaibench/worker_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from hardware.soaibench.phase_telemetry import run_phase_with_telemetry
from hardware.soaibench.telemetry import SoAIBenchTelemetryAccumulator
from hardware.soaibench.types import SoAIBenchProfile, SoAIBenchRunStatus
from hardware.soaibench.worker_runtime_conditions import (
    finish_cancelled_runtime_profile,
    finish_unstable_for_telemetry,
    persist_worker_heartbeat,
)
from hardware.soaibench.worker_terminal import finish_successful_runtime
from hardware.soaibench.workload import (
    SoAIBenchWorkloadResult,
    score_stress_phase,
)

if TYPE_CHECKING:
    from hardware.soaibench.internal_protocols import SoAIBenchOpenCLExecutionProtocol
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
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
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
            terminate_execution=opencl_pool.close,
        )
        if phase_run.terminal_telemetry is not None:
            await finish_unstable_for_telemetry(
                runtime_context=runtime_context,
                telemetry_accumulator=telemetry_accumulator,
                telemetry=phase_run.terminal_telemetry,
                terminate_execution=opencl_pool.close,
            )
            return
        if phase_run.phase_result is None:
            await opencl_pool.close()
            await finish_cancelled_runtime_profile(
                runtime_context=runtime_context,
                profile=SoAIBenchProfile.STRESS,
            )
            return
        latest_result = score_stress_phase(phase_run.phase_result)
        sample_count += latest_result.sample_count
        telemetry_summary = telemetry_accumulator.summary()
        summary = {
            **runtime_context.base_summary,
            **latest_result.summary,
            **telemetry_summary,
            "stress_sample_count": sample_count,
        }
        latest_summary = summary
        await persist_worker_heartbeat(
            runtime_context=runtime_context,
            event_context=event_context,
            summary=summary,
            sample_count=sample_count,
            progress_current=min(95, 10 + sample_count),
            status_message="SoAIBench stress slice completed.",
        )
    if latest_result is None:
        await opencl_pool.close()
        await finish_cancelled_runtime_profile(
            runtime_context=runtime_context,
            profile=SoAIBenchProfile.STRESS,
        )
        return
    await opencl_pool.close()
    stopped_by_user = runtime_context.stop_event.is_set()
    await finish_successful_runtime(
        runtime_context=runtime_context,
        status=SoAIBenchRunStatus.STOPPED if stopped_by_user else SoAIBenchRunStatus.COMPLETED,
        base_summary=latest_summary,
        result=latest_result,
        sample_count=sample_count,
    )


def _stress_duration_elapsed(
    started_at_monotonic: float,
    max_duration_seconds: float | None,
) -> bool:
    if max_duration_seconds is None:
        return False
    return time.monotonic() - started_at_monotonic >= max_duration_seconds


async def run_compute_phase(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    identity: SoAIBenchGpuIdentity,
    timeout_sec: float,
) -> SoAIBenchPhaseResult:
    return await opencl_pool.phase(
        "compute",
        identity,
        stress=False,
        timeout_sec=timeout_sec,
    )


async def run_alu_phase(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    identity: SoAIBenchGpuIdentity,
    timeout_sec: float,
) -> SoAIBenchPhaseResult:
    return await opencl_pool.phase(
        "alu",
        identity,
        stress=False,
        timeout_sec=timeout_sec,
    )


async def run_memory_phase(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    identity: SoAIBenchGpuIdentity,
    timeout_sec: float,
) -> SoAIBenchPhaseResult:
    return await opencl_pool.phase(
        "memory",
        identity,
        stress=False,
        timeout_sec=timeout_sec,
    )


async def run_latency_phase(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    identity: SoAIBenchGpuIdentity,
    timeout_sec: float,
) -> SoAIBenchPhaseResult:
    return await opencl_pool.phase(
        "latency",
        identity,
        stress=False,
        timeout_sec=timeout_sec,
    )


async def run_matrix_phase(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    identity: SoAIBenchGpuIdentity,
    timeout_sec: float,
) -> SoAIBenchPhaseResult:
    return await opencl_pool.phase(
        "matrix",
        identity,
        stress=False,
        timeout_sec=timeout_sec,
    )


async def run_mixed_phase(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    identity: SoAIBenchGpuIdentity,
    stress: bool,
    timeout_sec: float,
) -> SoAIBenchPhaseResult:
    return await opencl_pool.phase(
        "mixed",
        identity,
        stress=stress,
        timeout_sec=timeout_sec,
    )
