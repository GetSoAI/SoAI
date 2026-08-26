"""SoAI - SoAIBench standard worker execution [backend/hardware/soaibench/worker_standard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.enums import TaskStatus
from hardware.soaibench.scoring import (
    score_payload_with_stability_multiplier,
    score_telemetry_summary_fields,
)
from hardware.soaibench.types import SoAIBenchRunStatus
from hardware.soaibench.worker_standard_phases import run_standard_phases
from hardware.soaibench.worker_terminal import finish_success
from hardware.soaibench.workload import SoAIBenchWorkloadResult

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.types.json import JSONDict
    from hardware.soaibench.worker_context import SoAIBenchWorkerRuntimeContext

__all__ = ("run_standard",)


async def run_standard(
    *,
    opencl_pool: BoundedBlockingPool,
    runtime_context: SoAIBenchWorkerRuntimeContext,
) -> None:
    phase_result = await run_standard_phases(
        opencl_pool=opencl_pool,
        runtime_context=runtime_context,
    )
    if phase_result is None:
        return
    status = SoAIBenchRunStatus.COMPLETED
    task_status = TaskStatus.COMPLETED
    failure_reason: str | None = None
    result = phase_result.workload_result
    telemetry_summary = phase_result.telemetry_summary
    summary = {**runtime_context.base_summary, **telemetry_summary}
    terminal_result = _result_with_telemetry(result, telemetry_summary)
    if not telemetry_summary.get("telemetry_available"):
        terminal_result = _result_with_reduced_stability(terminal_result)
    await finish_success(
        database_hardware=runtime_context.database_hardware,
        task_registry=runtime_context.task_registry,
        run_id=runtime_context.run_id,
        task_id=runtime_context.task_id,
        status=status,
        task_status=task_status,
        started_at_ms=runtime_context.started_at_ms,
        base_summary=summary,
        result=terminal_result,
        sample_count=terminal_result.sample_count,
        failure_reason=failure_reason,
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
    )


def _result_with_reduced_stability(
    result: SoAIBenchWorkloadResult,
) -> SoAIBenchWorkloadResult:
    return SoAIBenchWorkloadResult(
        score_fields=score_payload_with_stability_multiplier(result.score_fields, 0.85),
        summary=result.summary,
        duration_ms=result.duration_ms,
        sample_count=result.sample_count,
    )
