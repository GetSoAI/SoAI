"""SoAI - SoAIBench certified pass execution [backend/hardware/soaibench/worker_certified_passes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING

from hardware.soaibench.phase_telemetry import PhaseTelemetryRunResult, run_phase_with_telemetry
from hardware.soaibench.runtime import (
    CERTIFIED_MEASURED_PASSES,
    CERTIFIED_WARMUP_PASSES,
)
from hardware.soaibench.worker_execution import (
    run_alu_phase,
    run_compute_phase,
    run_latency_phase,
    run_matrix_phase,
    run_memory_phase,
    run_mixed_phase,
)
from hardware.soaibench.workload import (
    SoAIBenchStandardPhases,
    SoAIBenchWorkloadResult,
    score_standard_phases,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.types.json import JSONDict
    from hardware.soaibench.internal_protocols import SoAIBenchOpenCLExecutionProtocol
    from hardware.soaibench.telemetry import (
        SoAIBenchTelemetryAccumulator,
        SoAIBenchTelemetrySnapshot,
    )
    from hardware.soaibench.types import SoAIBenchGpuIdentity
    from hardware.soaibench.worker_context import SoAIBenchWorkerRuntimeContext
    from hardware.soaibench.workload_common import SoAIBenchPhaseResult

    type CertifiedPhaseProgress = Callable[[str, int], Awaitable[None]]

__all__ = (
    "CertifiedPassRunResult",
    "certification_payload",
    "pass_payload",
    "run_certified_pass",
)

CERTIFIED_PHASE_TIMEOUT_SECONDS = 300.0
CERTIFIED_TELEMETRY_SAMPLE_INTERVAL_SECONDS = 0.25


@dataclass(frozen=True, slots=True)
class CertifiedPassRunResult:
    workload_result: SoAIBenchWorkloadResult | None
    terminal_telemetry: SoAIBenchTelemetrySnapshot | None


async def run_certified_pass(
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    identity: SoAIBenchGpuIdentity,
    stop_event: asyncio.Event,
    phase_progress: CertifiedPhaseProgress,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    telemetry_accumulator: SoAIBenchTelemetryAccumulator,
) -> CertifiedPassRunResult:
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    await phase_progress("compute", 1)
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    compute_run = await _run_monitored_phase(
        runtime_context,
        telemetry_accumulator,
        opencl_pool,
        run_compute_phase(
            opencl_pool=opencl_pool,
            identity=identity,
            timeout_sec=CERTIFIED_PHASE_TIMEOUT_SECONDS,
        ),
        "soaibench-certified-compute",
    )
    if compute_run.terminal_telemetry is not None:
        return CertifiedPassRunResult(None, compute_run.terminal_telemetry)
    if compute_run.phase_result is None and stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    compute = compute_run.require_phase_result()
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    await phase_progress("alu", 2)
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    alu_run = await _run_monitored_phase(
        runtime_context,
        telemetry_accumulator,
        opencl_pool,
        run_alu_phase(
            opencl_pool=opencl_pool,
            identity=identity,
            timeout_sec=CERTIFIED_PHASE_TIMEOUT_SECONDS,
        ),
        "soaibench-certified-alu",
    )
    if alu_run.terminal_telemetry is not None:
        return CertifiedPassRunResult(None, alu_run.terminal_telemetry)
    if alu_run.phase_result is None and stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    alu = alu_run.require_phase_result()
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    await phase_progress("matrix", 3)
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    matrix_run = await _run_monitored_phase(
        runtime_context,
        telemetry_accumulator,
        opencl_pool,
        run_matrix_phase(
            opencl_pool=opencl_pool,
            identity=identity,
            timeout_sec=CERTIFIED_PHASE_TIMEOUT_SECONDS,
        ),
        "soaibench-certified-matrix",
    )
    if matrix_run.terminal_telemetry is not None:
        return CertifiedPassRunResult(None, matrix_run.terminal_telemetry)
    if matrix_run.phase_result is None and stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    matrix = matrix_run.require_phase_result()
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    await phase_progress("latency", 4)
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    latency_run = await _run_monitored_phase(
        runtime_context,
        telemetry_accumulator,
        opencl_pool,
        run_latency_phase(
            opencl_pool=opencl_pool,
            identity=identity,
            timeout_sec=CERTIFIED_PHASE_TIMEOUT_SECONDS,
        ),
        "soaibench-certified-latency",
    )
    if latency_run.terminal_telemetry is not None:
        return CertifiedPassRunResult(None, latency_run.terminal_telemetry)
    if latency_run.phase_result is None and stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    latency = latency_run.require_phase_result()
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    await phase_progress("memory", 5)
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    memory_run = await _run_monitored_phase(
        runtime_context,
        telemetry_accumulator,
        opencl_pool,
        run_memory_phase(
            opencl_pool=opencl_pool,
            identity=identity,
            timeout_sec=CERTIFIED_PHASE_TIMEOUT_SECONDS,
        ),
        "soaibench-certified-memory",
    )
    if memory_run.terminal_telemetry is not None:
        return CertifiedPassRunResult(None, memory_run.terminal_telemetry)
    if memory_run.phase_result is None and stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    memory = memory_run.require_phase_result()
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    await phase_progress("stability", 6)
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    mixed_run = await _run_monitored_phase(
        runtime_context,
        telemetry_accumulator,
        opencl_pool,
        run_mixed_phase(
            opencl_pool=opencl_pool,
            identity=identity,
            stress=False,
            timeout_sec=CERTIFIED_PHASE_TIMEOUT_SECONDS,
        ),
        "soaibench-certified-mixed",
    )
    if mixed_run.terminal_telemetry is not None:
        return CertifiedPassRunResult(None, mixed_run.terminal_telemetry)
    if mixed_run.phase_result is None and stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    mixed = mixed_run.require_phase_result()
    if stop_event.is_set():
        return CertifiedPassRunResult(None, None)
    return CertifiedPassRunResult(
        score_standard_phases(
            SoAIBenchStandardPhases(alu, compute, matrix, memory, mixed, latency)
        ),
        None,
    )


async def _run_monitored_phase(
    runtime_context: SoAIBenchWorkerRuntimeContext,
    telemetry_accumulator: SoAIBenchTelemetryAccumulator,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    awaitable: Coroutine[None, None, SoAIBenchPhaseResult],
    task_name: str,
) -> PhaseTelemetryRunResult:
    return await run_phase_with_telemetry(
        awaitable=awaitable,
        task_name=task_name,
        runtime_context=runtime_context,
        telemetry_accumulator=telemetry_accumulator,
        sample_interval_seconds=CERTIFIED_TELEMETRY_SAMPLE_INTERVAL_SECONDS,
        terminate_execution=opencl_pool.close,
    )


def pass_payload(
    index: int,
    result: SoAIBenchWorkloadResult,
    telemetry: JSONDict,
    *,
    warmup: bool,
) -> JSONDict:
    return {
        "index": index,
        "warmup": warmup,
        **result.score_fields,
        "duration_ms": result.duration_ms,
        "sample_count": result.sample_count,
        "telemetry": telemetry,
        "workload": result.summary,
    }


def certification_payload(result: SoAIBenchWorkloadResult) -> JSONDict:
    return {
        "mode": "certified",
        "warmup_pass_count": CERTIFIED_WARMUP_PASSES,
        "measured_pass_count": CERTIFIED_MEASURED_PASSES,
        "leaderboard_eligible": result.summary.get("leaderboard_eligible") is True,
        "leaderboard_rejection_reason": result.summary.get("leaderboard_rejection_reason"),
        "score_variance_percent": result.summary.get("score_variance_percent"),
        "phase_variation_percent": result.summary.get("phase_variation_percent"),
        "phase_drift_percent": result.summary.get("phase_drift_percent"),
        "score_confidence": result.summary.get("score_confidence"),
    }
