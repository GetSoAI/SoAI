"""SoAI - SoAIBench certified standard worker [backend/hardware/soaibench/worker_certified.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from core.tasks.enums import TaskStatus
from hardware.soaibench.certification import certified_result
from hardware.soaibench.environment import build_soaibench_environment
from hardware.soaibench.runtime import (
    CERTIFIED_MEASURED_PASSES,
    CERTIFIED_WARMUP_PASSES,
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
    publish_certified_progress,
)
from hardware.soaibench.worker_runtime_conditions import (
    finish_cancelled_if_stopped,
    read_telemetry_or_finish_unstable,
)
from hardware.soaibench.worker_terminal import finish_success

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.types.json import JSONDict
    from hardware.soaibench.worker_context import (
        SoAIBenchWorkerEventContext,
        SoAIBenchWorkerRuntimeContext,
    )

__all__ = ("run_certified_standard",)


async def run_certified_standard(
    *,
    opencl_pool: BoundedBlockingPool,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    event_context: SoAIBenchWorkerEventContext,
) -> None:
    telemetry_accumulator = SoAIBenchTelemetryAccumulator()
    warmup_passes: list[JSONDict] = []
    measured_passes: list[JSONDict] = []
    for pass_index in range(CERTIFIED_WARMUP_PASSES):
        if await finish_cancelled_if_stopped(
            runtime_context=runtime_context,
        ):
            return
        publish_warmup_phase = build_certified_phase_progress_publisher(
            runtime_context=runtime_context,
            event_context=event_context,
            telemetry_accumulator=telemetry_accumulator,
            warmup_passes=warmup_passes,
            measured_passes=measured_passes,
            pass_type="warmup",
            pass_index=pass_index + 1,
            pass_total=CERTIFIED_WARMUP_PASSES,
        )
        warmup = await run_certified_pass(
            opencl_pool,
            runtime_context.identity,
            runtime_context.stop_event,
            publish_warmup_phase,
        )
        if warmup is None:
            await finish_cancelled_if_stopped(
                runtime_context=runtime_context,
            )
            return
        telemetry = await read_telemetry_or_finish_unstable(
            runtime_context=runtime_context,
            telemetry_accumulator=telemetry_accumulator,
        )
        if telemetry is None:
            return
        warmup_passes.append(pass_payload(pass_index + 1, warmup, telemetry.summary, warmup=True))
        await publish_certified_progress(
            runtime_context=runtime_context,
            event_context=event_context,
            telemetry_summary=telemetry_accumulator.summary(),
            warmup_passes=warmup_passes,
            measured_passes=measured_passes,
            progress_current=5,
        )
    for pass_index in range(CERTIFIED_MEASURED_PASSES):
        if await finish_cancelled_if_stopped(
            runtime_context=runtime_context,
        ):
            return
        publish_measured_phase = build_certified_phase_progress_publisher(
            runtime_context=runtime_context,
            event_context=event_context,
            telemetry_accumulator=telemetry_accumulator,
            warmup_passes=warmup_passes,
            measured_passes=measured_passes,
            pass_type="measured",
            pass_index=pass_index + 1,
            pass_total=CERTIFIED_MEASURED_PASSES,
        )
        measured = await run_certified_pass(
            opencl_pool,
            runtime_context.identity,
            runtime_context.stop_event,
            publish_measured_phase,
        )
        if measured is None:
            await finish_cancelled_if_stopped(
                runtime_context=runtime_context,
            )
            return
        telemetry = await read_telemetry_or_finish_unstable(
            runtime_context=runtime_context,
            telemetry_accumulator=telemetry_accumulator,
        )
        if telemetry is None:
            return
        measured_passes.append(
            pass_payload(pass_index + 1, measured, telemetry.summary, warmup=False),
        )
        await publish_certified_progress(
            runtime_context=runtime_context,
            event_context=event_context,
            telemetry_summary=telemetry_accumulator.summary(),
            warmup_passes=warmup_passes,
            measured_passes=measured_passes,
            progress_current=10 + ((pass_index + 1) * 16),
        )
    telemetry_summary = telemetry_accumulator.summary()
    result = certified_result(
        measured_passes=measured_passes,
        telemetry_summary=telemetry_summary,
        temperature_limit_celsius=runtime_context.temperature_limit_celsius,
    )
    summary = {**runtime_context.base_summary, **telemetry_summary, **result.summary}
    environment = await build_soaibench_environment(
        hardware_manager=runtime_context.hardware_manager,
        identity=runtime_context.identity,
        workload_summary={**measured_passes[-1], **summary},
    )
    pass_results = {"warmup": warmup_passes, "measured": measured_passes}
    await finish_success(
        database_hardware=runtime_context.database_hardware,
        task_registry=runtime_context.task_registry,
        run_id=runtime_context.run_id,
        task_id=runtime_context.task_id,
        status=SoAIBenchRunStatus.COMPLETED,
        task_status=TaskStatus.COMPLETED,
        started_at_ms=runtime_context.started_at_ms,
        base_summary=summary,
        result=result,
        sample_count=result.sample_count,
        terminal_fields={
            "pass_results_json": serialize_json_compact_stable(pass_results),
            "environment_json": serialize_json_compact_stable(environment),
            "certification_json": serialize_json_compact_stable(certification_payload(result)),
            "leaderboard_eligible": result.summary.get("leaderboard_eligible") is True,
            "leaderboard_rejection_reason": result.summary.get("leaderboard_rejection_reason"),
            "score_variance_percent": result.summary.get("score_variance_percent"),
        },
    )
