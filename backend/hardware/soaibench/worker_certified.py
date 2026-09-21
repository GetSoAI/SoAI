"""SoAI - SoAIBench certified standard worker [backend/hardware/soaibench/worker_certified.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.serialization.json import serialize_json_compact_stable
from hardware.soaibench.certification import certified_result
from hardware.soaibench.environment import build_soaibench_environment
from hardware.soaibench.runtime import (
    CERTIFIED_MEASURED_PASSES,
    CERTIFIED_WARMUP_PASSES,
    CERTIFIED_WARMUP_SECONDS,
)
from hardware.soaibench.telemetry import SoAIBenchTelemetryAccumulator
from hardware.soaibench.types import SoAIBenchRunStatus
from hardware.soaibench.worker_certified_passes import (
    certification_payload,
    pass_payload,
    run_certified_pass,
)
from hardware.soaibench.worker_certified_support import (
    build_certified_phase_progress_publisher,
    certified_warmup_progress,
    publish_certified_progress,
)
from hardware.soaibench.worker_runtime_conditions import (
    finish_cancelled_if_stopped,
    finish_unstable_for_telemetry,
    read_telemetry_or_finish_unstable,
)
from hardware.soaibench.worker_terminal import finish_successful_runtime

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.soaibench.internal_protocols import SoAIBenchOpenCLExecutionProtocol
    from hardware.soaibench.worker_context import (
        SoAIBenchWorkerEventContext,
        SoAIBenchWorkerRuntimeContext,
    )
    from hardware.soaibench.workload import SoAIBenchWorkloadResult

__all__ = ("run_certified_standard",)


async def run_certified_standard(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    event_context: SoAIBenchWorkerEventContext,
) -> None:
    warmup_telemetry_accumulator = SoAIBenchTelemetryAccumulator()
    measured_telemetry_accumulator = SoAIBenchTelemetryAccumulator()
    warmup_passes: list[JSONDict] = []
    measured_passes: list[JSONDict] = []
    last_measured_result: SoAIBenchWorkloadResult | None = None
    warmup_active_seconds = 0.0
    warmup_cycle_count = 0
    warmup_progress = 0
    warmup_result: SoAIBenchWorkloadResult | None = None
    warmup_telemetry_summary: JSONDict | None = None
    while warmup_active_seconds < CERTIFIED_WARMUP_SECONDS:
        if await finish_cancelled_if_stopped(
            runtime_context=runtime_context,
            terminate_execution=opencl_pool.close,
        ):
            return
        publish_warmup_phase = build_certified_phase_progress_publisher(
            runtime_context=runtime_context,
            event_context=event_context,
            telemetry_accumulator=warmup_telemetry_accumulator,
            warmup_passes=warmup_passes,
            measured_passes=measured_passes,
            pass_type="warmup",
            pass_index=1,
            pass_total=CERTIFIED_WARMUP_PASSES,
            minimum_progress=warmup_progress,
        )
        warmup_run = await run_certified_pass(
            opencl_pool,
            runtime_context.identity,
            runtime_context.stop_event,
            publish_warmup_phase,
            runtime_context,
            warmup_telemetry_accumulator,
        )
        if warmup_run.terminal_telemetry is not None:
            await finish_unstable_for_telemetry(
                runtime_context=runtime_context,
                telemetry_accumulator=warmup_telemetry_accumulator,
                telemetry=warmup_run.terminal_telemetry,
                terminate_execution=opencl_pool.close,
            )
            return
        warmup = warmup_run.workload_result
        if warmup is None:
            await finish_cancelled_if_stopped(
                runtime_context=runtime_context,
                terminate_execution=opencl_pool.close,
            )
            return
        telemetry = await read_telemetry_or_finish_unstable(
            runtime_context=runtime_context,
            telemetry_accumulator=warmup_telemetry_accumulator,
            terminate_execution=opencl_pool.close,
        )
        if telemetry is None:
            return
        warmup_active_seconds += warmup.active_seconds
        warmup_cycle_count += 1
        warmup_progress = certified_warmup_progress(
            warmup_active_seconds,
            CERTIFIED_WARMUP_SECONDS,
            warmup_progress,
        )
        warmup_result = warmup
        warmup_telemetry_summary = telemetry.summary
        await publish_certified_progress(
            runtime_context=runtime_context,
            event_context=event_context,
            telemetry_summary=warmup_telemetry_accumulator.summary(),
            warmup_passes=warmup_passes,
            measured_passes=measured_passes,
            progress_current=warmup_progress,
        )
    if warmup_result is None or warmup_telemetry_summary is None:
        raise StateError("Certified warm-up workload evidence is incomplete.")
    warmup_passes.append(pass_payload(1, warmup_result, warmup_telemetry_summary, warmup=True))
    for pass_index in range(CERTIFIED_MEASURED_PASSES):
        if await finish_cancelled_if_stopped(
            runtime_context=runtime_context,
            terminate_execution=opencl_pool.close,
        ):
            return
        publish_measured_phase = build_certified_phase_progress_publisher(
            runtime_context=runtime_context,
            event_context=event_context,
            telemetry_accumulator=measured_telemetry_accumulator,
            warmup_passes=warmup_passes,
            measured_passes=measured_passes,
            pass_type="measured",
            pass_index=pass_index + 1,
            pass_total=CERTIFIED_MEASURED_PASSES,
            minimum_progress=10 + (pass_index * 16),
        )
        measured_run = await run_certified_pass(
            opencl_pool,
            runtime_context.identity,
            runtime_context.stop_event,
            publish_measured_phase,
            runtime_context,
            measured_telemetry_accumulator,
        )
        if measured_run.terminal_telemetry is not None:
            await finish_unstable_for_telemetry(
                runtime_context=runtime_context,
                telemetry_accumulator=measured_telemetry_accumulator,
                telemetry=measured_run.terminal_telemetry,
                terminate_execution=opencl_pool.close,
            )
            return
        measured = measured_run.workload_result
        if measured is None:
            await finish_cancelled_if_stopped(
                runtime_context=runtime_context,
                terminate_execution=opencl_pool.close,
            )
            return
        telemetry = await read_telemetry_or_finish_unstable(
            runtime_context=runtime_context,
            telemetry_accumulator=measured_telemetry_accumulator,
            terminate_execution=opencl_pool.close,
        )
        if telemetry is None:
            return
        measured_passes.append(
            pass_payload(pass_index + 1, measured, telemetry.summary, warmup=False),
        )
        last_measured_result = measured
        await publish_certified_progress(
            runtime_context=runtime_context,
            event_context=event_context,
            telemetry_summary=measured_telemetry_accumulator.summary(),
            warmup_passes=warmup_passes,
            measured_passes=measured_passes,
            progress_current=10 + ((pass_index + 1) * 16),
        )
    telemetry_summary = measured_telemetry_accumulator.summary()
    result = certified_result(
        measured_passes=measured_passes,
        telemetry_summary=telemetry_summary,
    )
    if last_measured_result is None or len(measured_passes) != CERTIFIED_MEASURED_PASSES:
        raise StateError("Certified measured workload evidence is incomplete.")
    await opencl_pool.close()
    summary = {
        **runtime_context.base_summary,
        **telemetry_summary,
        **result.summary,
        "warmup_active_seconds": round(warmup_active_seconds, 6),
        "warmup_cycle_count": warmup_cycle_count,
    }
    environment = build_soaibench_environment(
        identity=runtime_context.identity,
        settings_snapshot=runtime_context.settings_snapshot,
        preflight_summary=runtime_context.base_summary,
        workload_summary=last_measured_result.summary,
    )
    pass_results = {"warmup": warmup_passes, "measured": measured_passes}
    await finish_successful_runtime(
        runtime_context=runtime_context,
        status=SoAIBenchRunStatus.COMPLETED,
        base_summary=summary,
        result=result,
        sample_count=result.sample_count,
        terminal_fields={
            "duration_ms": result.duration_ms,
            "pass_results_json": serialize_json_compact_stable(pass_results),
            "environment_json": serialize_json_compact_stable(environment),
            "certification_json": serialize_json_compact_stable(certification_payload(result)),
            "leaderboard_eligible": result.summary.get("leaderboard_eligible") is True,
            "leaderboard_rejection_reason": result.summary.get("leaderboard_rejection_reason"),
            "score_variance_percent": result.summary.get("score_variance_percent"),
        },
    )
