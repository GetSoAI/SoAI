"""SoAI - SoAIBench worker runtime condition handling [backend/hardware/soaibench/worker_runtime_conditions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from hardware.soaibench.telemetry import read_soaibench_telemetry_snapshot
from hardware.soaibench.types import SoAIBenchProfile
from hardware.soaibench.worker_terminal import finish_cancelled, finish_unstable

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.soaibench.telemetry import (
        SoAIBenchTelemetryAccumulator,
        SoAIBenchTelemetrySnapshot,
    )
    from hardware.soaibench.worker_context import SoAIBenchWorkerRuntimeContext

__all__ = (
    "finish_cancelled_if_stopped",
    "finish_cancelled_runtime_profile",
    "read_telemetry_or_finish_unstable",
)


async def read_telemetry_or_finish_unstable(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    telemetry_accumulator: SoAIBenchTelemetryAccumulator,
) -> SoAIBenchTelemetrySnapshot | None:
    telemetry = await read_soaibench_telemetry_snapshot(
        runtime_context.hardware_manager,
        device_id=runtime_context.identity.device_id,
        temperature_limit_celsius=runtime_context.temperature_limit_celsius,
    )
    telemetry_accumulator.add(telemetry)
    if not telemetry.temperature_exceeded:
        return telemetry
    await finish_unstable(
        database_hardware=runtime_context.database_hardware,
        task_registry=runtime_context.task_registry,
        run_id=runtime_context.run_id,
        task_id=runtime_context.task_id,
        started_at_ms=runtime_context.started_at_ms,
        base_summary={**runtime_context.base_summary, **telemetry_accumulator.summary()},
        reason=telemetry.instability_reason or "temperature_limit_exceeded",
        message=telemetry.instability_message or "GPU temperature limit exceeded.",
    )
    return None


async def finish_cancelled_if_stopped(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    base_summary: JSONDict | None = None,
) -> bool:
    if not runtime_context.stop_event.is_set():
        return False
    await finish_cancelled_runtime_profile(
        runtime_context=runtime_context,
        profile=SoAIBenchProfile.STANDARD,
        base_summary=base_summary,
    )
    return True


async def finish_cancelled_runtime_profile(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    profile: SoAIBenchProfile,
    base_summary: JSONDict | None = None,
) -> None:
    await finish_cancelled(
        database_hardware=runtime_context.database_hardware,
        task_registry=runtime_context.task_registry,
        run_id=runtime_context.run_id,
        task_id=runtime_context.task_id,
        started_at_ms=runtime_context.started_at_ms,
        base_summary=base_summary or runtime_context.base_summary,
        profile=profile,
        stop_event=runtime_context.stop_event,
    )
