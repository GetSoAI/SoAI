"""SoAI - SoAIBench certified progress support [backend/hardware/soaibench/worker_certified_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.integers import coerce_non_negative_exact_int_or_zero
from hardware.soaibench.worker_runtime_conditions import persist_worker_heartbeat

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.types.json import JSONDict
    from hardware.soaibench.telemetry import SoAIBenchTelemetryAccumulator
    from hardware.soaibench.worker_context import (
        SoAIBenchWorkerEventContext,
        SoAIBenchWorkerRuntimeContext,
    )

    type CertifiedPhaseProgress = Callable[[str, int], Awaitable[None]]

__all__ = (
    "CERTIFIED_PHASE_TOTAL",
    "build_certified_phase_progress_publisher",
    "certified_phase_progress",
    "certified_warmup_progress",
    "publish_certified_phase_progress",
    "publish_certified_progress",
)

CERTIFIED_PHASE_TOTAL = 6
MEASURED_PHASE_PROGRESS_OFFSETS = (0, 3, 5, 8, 11, 14)


def build_certified_phase_progress_publisher(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    event_context: SoAIBenchWorkerEventContext,
    telemetry_accumulator: SoAIBenchTelemetryAccumulator,
    warmup_passes: list[JSONDict],
    measured_passes: list[JSONDict],
    pass_type: str,
    pass_index: int,
    pass_total: int,
    minimum_progress: int,
) -> CertifiedPhaseProgress:
    async def publish_phase(phase: str, phase_index: int) -> None:
        await publish_certified_phase_progress(
            runtime_context=runtime_context,
            event_context=event_context,
            telemetry_summary=telemetry_accumulator.summary(),
            warmup_passes=warmup_passes,
            measured_passes=measured_passes,
            pass_type=pass_type,
            pass_index=pass_index,
            pass_total=pass_total,
            phase=phase,
            phase_index=phase_index,
            minimum_progress=minimum_progress,
        )

    return publish_phase


async def publish_certified_progress(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    event_context: SoAIBenchWorkerEventContext,
    telemetry_summary: JSONDict,
    warmup_passes: list[JSONDict],
    measured_passes: list[JSONDict],
    progress_current: int,
) -> None:
    summary = {
        **runtime_context.base_summary,
        **telemetry_summary,
        "benchmark_mode": "certified",
        "warmup_passes_completed": len(warmup_passes),
        "measured_passes_completed": len(measured_passes),
        "progress_percent": progress_current,
    }
    await _publish_certified_summary(
        runtime_context=runtime_context,
        event_context=event_context,
        summary=summary,
        measured_passes=measured_passes,
        progress_current=progress_current,
        status_message="SoAIBench certified pass completed.",
    )


async def publish_certified_phase_progress(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    event_context: SoAIBenchWorkerEventContext,
    telemetry_summary: JSONDict,
    warmup_passes: list[JSONDict],
    measured_passes: list[JSONDict],
    pass_type: str,
    pass_index: int,
    pass_total: int,
    phase: str,
    phase_index: int,
    minimum_progress: int = 0,
) -> None:
    progress_current = certified_phase_progress(
        pass_type=pass_type,
        pass_index=pass_index,
        phase_index=phase_index,
    )
    progress_current = max(minimum_progress, progress_current)
    gpu_name = runtime_context.identity.gpu_name or runtime_context.identity.device_id
    gpu_index = runtime_context.identity.gpu_index
    gpu_number = str(gpu_index) if gpu_index is not None else "unknown"
    summary = {
        **runtime_context.base_summary,
        **telemetry_summary,
        "benchmark_mode": "certified",
        "warmup_passes_completed": len(warmup_passes),
        "measured_passes_completed": len(measured_passes),
        "current_pass_type": pass_type,
        "current_pass_index": pass_index,
        "current_pass_total": pass_total,
        "current_phase": phase,
        "current_phase_index": phase_index,
        "current_phase_total": CERTIFIED_PHASE_TOTAL,
        "progress_percent": progress_current,
    }
    await _publish_certified_summary(
        runtime_context=runtime_context,
        event_context=event_context,
        summary=summary,
        measured_passes=measured_passes,
        progress_current=progress_current,
        status_message=(
            f"SoAIBench {pass_type} {pass_index} {phase} phase running "
            f"on GPU {gpu_number} ({gpu_name})."
        ),
    )


def certified_phase_progress(
    *,
    pass_type: str,
    pass_index: int,
    phase_index: int,
) -> int:
    if pass_type == "warmup":
        return max(1, min(5, phase_index))
    normalized_phase_index = max(1, min(CERTIFIED_PHASE_TOTAL, phase_index))
    phase_offset = MEASURED_PHASE_PROGRESS_OFFSETS[normalized_phase_index - 1]
    return min(94, 10 + ((max(1, pass_index) - 1) * 16) + phase_offset)


def certified_warmup_progress(
    completed_active_seconds: float,
    required_active_seconds: float,
    previous_progress: int,
) -> int:
    return min(
        9,
        max(
            previous_progress,
            5,
            round(completed_active_seconds / required_active_seconds * 9),
        ),
    )


async def _publish_certified_summary(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    event_context: SoAIBenchWorkerEventContext,
    summary: JSONDict,
    measured_passes: list[JSONDict],
    progress_current: int,
    status_message: str,
) -> None:
    await persist_worker_heartbeat(
        runtime_context=runtime_context,
        event_context=event_context,
        summary=summary,
        sample_count=sum(
            coerce_non_negative_exact_int_or_zero(entry.get("sample_count"))
            for entry in measured_passes
        ),
        progress_current=progress_current,
        status_message=status_message,
    )
