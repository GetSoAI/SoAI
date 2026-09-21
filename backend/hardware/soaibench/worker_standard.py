"""SoAI - SoAIBench standard worker execution [backend/hardware/soaibench/worker_standard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from hardware.soaibench.scoring import score_telemetry_summary_fields
from hardware.soaibench.types import SoAIBenchRunStatus
from hardware.soaibench.worker_standard_phases import run_standard_phases
from hardware.soaibench.worker_terminal import finish_successful_runtime
from hardware.soaibench.workload import SoAIBenchWorkloadResult

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.soaibench.internal_protocols import SoAIBenchOpenCLExecutionProtocol
    from hardware.soaibench.worker_context import SoAIBenchWorkerRuntimeContext

__all__ = ("run_standard",)


async def run_standard(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    runtime_context: SoAIBenchWorkerRuntimeContext,
) -> None:
    phase_result = await run_standard_phases(
        opencl_pool=opencl_pool,
        runtime_context=runtime_context,
    )
    if phase_result is None:
        return
    result = phase_result.workload_result
    telemetry_summary = phase_result.telemetry_summary
    await opencl_pool.close()
    summary = {**runtime_context.base_summary, **telemetry_summary}
    terminal_result = _result_with_telemetry(result, telemetry_summary)
    await finish_successful_runtime(
        runtime_context=runtime_context,
        status=SoAIBenchRunStatus.COMPLETED,
        base_summary=summary,
        result=terminal_result,
        sample_count=terminal_result.sample_count,
        failure_reason=None,
    )


def _result_with_telemetry(
    result: SoAIBenchWorkloadResult,
    telemetry_summary: JSONDict,
) -> SoAIBenchWorkloadResult:
    return SoAIBenchWorkloadResult(
        score_fields={**result.score_fields, **score_telemetry_summary_fields(telemetry_summary)},
        summary=result.summary,
        duration_ms=result.duration_ms,
        sample_count=result.sample_count,
        active_seconds=result.active_seconds,
    )
