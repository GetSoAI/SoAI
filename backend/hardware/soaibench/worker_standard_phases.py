"""SoAI - SoAIBench standard phase sequencing [backend/hardware/soaibench/worker_standard_phases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.tasks.status_transitions import update_progress
from hardware.soaibench.phase_telemetry import PhaseTelemetryRunResult, run_phase_with_telemetry
from hardware.soaibench.telemetry import SoAIBenchTelemetryAccumulator
from hardware.soaibench.worker_execution import (
    run_alu_phase,
    run_compute_phase,
    run_latency_phase,
    run_matrix_phase,
    run_memory_phase,
    run_mixed_phase,
)
from hardware.soaibench.worker_runtime_conditions import (
    finish_cancelled_if_stopped,
    finish_unstable_for_telemetry,
    read_telemetry_or_finish_unstable,
)
from hardware.soaibench.workload import (
    SoAIBenchStandardPhases,
    SoAIBenchWorkloadResult,
    score_standard_phases,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.soaibench.internal_protocols import SoAIBenchOpenCLExecutionProtocol
    from hardware.soaibench.worker_context import SoAIBenchWorkerRuntimeContext
    from hardware.soaibench.workload_common import SoAIBenchPhaseResult

__all__ = ("STANDARD_PHASE_TIMEOUT_SECONDS", "StandardPhaseRunResult", "run_standard_phases")

STANDARD_PHASE_TIMEOUT_SECONDS = 300.0
STANDARD_TELEMETRY_SAMPLE_INTERVAL_SECONDS = 0.25


@dataclass(frozen=True, slots=True)
class StandardPhaseRunResult:
    workload_result: SoAIBenchWorkloadResult
    telemetry_summary: JSONDict


@dataclass(frozen=True, slots=True)
class StandardPhaseCheckpoint:
    opencl_pool: SoAIBenchOpenCLExecutionProtocol
    runtime_context: SoAIBenchWorkerRuntimeContext
    telemetry_accumulator: SoAIBenchTelemetryAccumulator


async def run_standard_phases(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    runtime_context: SoAIBenchWorkerRuntimeContext,
) -> StandardPhaseRunResult | None:
    checkpoint = StandardPhaseCheckpoint(
        opencl_pool=opencl_pool,
        runtime_context=runtime_context,
        telemetry_accumulator=SoAIBenchTelemetryAccumulator(),
    )
    if await _cancelled(checkpoint):
        return None
    compute_run = await _run_monitored_phase(
        checkpoint,
        run_compute_phase(
            opencl_pool=opencl_pool,
            identity=runtime_context.identity,
            timeout_sec=STANDARD_PHASE_TIMEOUT_SECONDS,
        ),
        "soaibench-standard-compute",
    )
    if not await _checkpoint(
        checkpoint,
        compute_run,
        30,
        "SoAIBench compute phase completed.",
    ):
        return None
    compute = compute_run.require_phase_result()
    alu_run = await _run_monitored_phase(
        checkpoint,
        run_alu_phase(
            opencl_pool=opencl_pool,
            identity=runtime_context.identity,
            timeout_sec=STANDARD_PHASE_TIMEOUT_SECONDS,
        ),
        "soaibench-standard-alu",
    )
    if not await _checkpoint(checkpoint, alu_run, 48, "SoAIBench ALU phase completed."):
        return None
    alu = alu_run.require_phase_result()
    matrix_run = await _run_monitored_phase(
        checkpoint,
        run_matrix_phase(
            opencl_pool=opencl_pool,
            identity=runtime_context.identity,
            timeout_sec=STANDARD_PHASE_TIMEOUT_SECONDS,
        ),
        "soaibench-standard-matrix",
    )
    if not await _checkpoint(checkpoint, matrix_run, 62, "SoAIBench matrix phase completed."):
        return None
    matrix = matrix_run.require_phase_result()
    latency_run = await _run_monitored_phase(
        checkpoint,
        run_latency_phase(
            opencl_pool=opencl_pool,
            identity=runtime_context.identity,
            timeout_sec=STANDARD_PHASE_TIMEOUT_SECONDS,
        ),
        "soaibench-standard-latency",
    )
    if not await _checkpoint(checkpoint, latency_run, 70, "SoAIBench latency phase completed."):
        return None
    latency = latency_run.require_phase_result()
    memory_run = await _run_monitored_phase(
        checkpoint,
        run_memory_phase(
            opencl_pool=opencl_pool,
            identity=runtime_context.identity,
            timeout_sec=STANDARD_PHASE_TIMEOUT_SECONDS,
        ),
        "soaibench-standard-memory",
    )
    if not await _checkpoint(checkpoint, memory_run, 82, "SoAIBench memory phase completed."):
        return None
    memory = memory_run.require_phase_result()
    mixed_run = await _run_monitored_phase(
        checkpoint,
        run_mixed_phase(
            opencl_pool=opencl_pool,
            identity=runtime_context.identity,
            stress=False,
            timeout_sec=STANDARD_PHASE_TIMEOUT_SECONDS,
        ),
        "soaibench-standard-mixed",
    )
    if not await _checkpoint(checkpoint, mixed_run, 90, "SoAIBench mixed phase completed."):
        return None
    mixed = mixed_run.require_phase_result()
    return StandardPhaseRunResult(
        workload_result=score_standard_phases(
            SoAIBenchStandardPhases(alu, compute, matrix, memory, mixed, latency)
        ),
        telemetry_summary=checkpoint.telemetry_accumulator.summary(),
    )


async def _run_monitored_phase(
    checkpoint: StandardPhaseCheckpoint,
    awaitable: Coroutine[None, None, SoAIBenchPhaseResult],
    task_name: str,
) -> PhaseTelemetryRunResult:
    phase_run = await run_phase_with_telemetry(
        awaitable=awaitable,
        task_name=task_name,
        runtime_context=checkpoint.runtime_context,
        telemetry_accumulator=checkpoint.telemetry_accumulator,
        sample_interval_seconds=STANDARD_TELEMETRY_SAMPLE_INTERVAL_SECONDS,
        terminate_execution=checkpoint.opencl_pool.close,
    )
    return phase_run


async def _checkpoint(
    checkpoint: StandardPhaseCheckpoint,
    phase_run: PhaseTelemetryRunResult,
    progress_current: int,
    status_message: str,
) -> bool:
    terminal_telemetry = phase_run.terminal_telemetry
    if terminal_telemetry is not None:
        await finish_unstable_for_telemetry(
            runtime_context=checkpoint.runtime_context,
            telemetry_accumulator=checkpoint.telemetry_accumulator,
            telemetry=terminal_telemetry,
            terminate_execution=checkpoint.opencl_pool.close,
        )
        return False
    await update_progress(
        checkpoint.runtime_context.task_registry,
        checkpoint.runtime_context.task_id,
        progress_current,
        status_message=status_message,
    )
    telemetry = await read_telemetry_or_finish_unstable(
        runtime_context=checkpoint.runtime_context,
        telemetry_accumulator=checkpoint.telemetry_accumulator,
        terminate_execution=checkpoint.opencl_pool.close,
    )
    return telemetry is not None and not await _cancelled(checkpoint)


async def _cancelled(checkpoint: StandardPhaseCheckpoint) -> bool:
    return await finish_cancelled_if_stopped(
        runtime_context=checkpoint.runtime_context,
        base_summary={
            **checkpoint.runtime_context.base_summary,
            **checkpoint.telemetry_accumulator.summary(),
        },
        terminate_execution=checkpoint.opencl_pool.close,
    )
