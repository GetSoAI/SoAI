"""SoAI - SoAIBench phase execution with active telemetry sampling [backend/hardware/soaibench/phase_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from hardware.soaibench.telemetry import read_soaibench_telemetry_snapshot

if TYPE_CHECKING:
    from hardware.soaibench.telemetry import (
        SoAIBenchTelemetryAccumulator,
        SoAIBenchTelemetrySnapshot,
    )
    from hardware.soaibench.worker_context import SoAIBenchWorkerRuntimeContext
    from hardware.soaibench.workload_common import SoAIBenchPhaseResult

__all__ = ("PhaseTelemetryRunResult", "run_phase_with_telemetry")


@dataclass(frozen=True, slots=True)
class PhaseTelemetryRunResult:
    phase_result: SoAIBenchPhaseResult
    terminal_telemetry: SoAIBenchTelemetrySnapshot | None


async def run_phase_with_telemetry(
    *,
    awaitable: Coroutine[None, None, SoAIBenchPhaseResult],
    task_name: str,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    telemetry_accumulator: SoAIBenchTelemetryAccumulator,
    sample_interval_seconds: float,
) -> PhaseTelemetryRunResult:
    phase_task = create_ephemeral_task(awaitable, name=task_name, log_exceptions=False)
    terminal_telemetry: SoAIBenchTelemetrySnapshot | None = None
    try:
        while not phase_task.done():
            telemetry = await read_soaibench_telemetry_snapshot(
                runtime_context.hardware_manager,
                device_id=runtime_context.identity.device_id,
                temperature_limit_celsius=runtime_context.temperature_limit_celsius,
            )
            telemetry_accumulator.add(telemetry)
            if telemetry.temperature_exceeded:
                terminal_telemetry = telemetry
            if phase_task.done():
                break
            try:
                await asyncio.wait_for(
                    asyncio.shield(phase_task),
                    timeout=sample_interval_seconds,
                )
            except TimeoutError:
                continue
        return PhaseTelemetryRunResult(
            phase_result=await phase_task,
            terminal_telemetry=terminal_telemetry,
        )
    finally:
        if not phase_task.done():
            await cancel_and_await((phase_task,), task_label=task_name)
