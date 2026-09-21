"""SoAI - SoAIBench phase execution with active telemetry sampling [backend/hardware/soaibench/phase_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exceptions import StateError
from hardware.soaibench.worker_runtime_conditions import read_worker_telemetry

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
    phase_result: SoAIBenchPhaseResult | None
    terminal_telemetry: SoAIBenchTelemetrySnapshot | None

    def require_phase_result(self) -> SoAIBenchPhaseResult:
        if self.phase_result is None:
            raise StateError("SoAIBench phase result is unavailable after interruption.")
        return self.phase_result


async def run_phase_with_telemetry(
    *,
    awaitable: Coroutine[None, None, SoAIBenchPhaseResult],
    task_name: str,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    telemetry_accumulator: SoAIBenchTelemetryAccumulator,
    sample_interval_seconds: float,
    terminate_execution: Callable[[], Awaitable[None]] | None = None,
) -> PhaseTelemetryRunResult:
    phase_task = create_ephemeral_task(awaitable, name=task_name, log_exceptions=False)
    terminal_telemetry: SoAIBenchTelemetrySnapshot | None = None
    try:
        while not phase_task.done():
            if runtime_context.stop_event.is_set():
                return PhaseTelemetryRunResult(None, None)
            telemetry = await read_worker_telemetry(
                runtime_context=runtime_context,
                accumulator=telemetry_accumulator,
            )
            if telemetry.temperature_exceeded:
                terminal_telemetry = telemetry
                return PhaseTelemetryRunResult(
                    phase_result=None,
                    terminal_telemetry=terminal_telemetry,
                )
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
            try:
                await uncancel_then_cleanup(cancel_and_await((phase_task,), task_label=task_name))
            finally:
                if terminate_execution is not None:
                    await uncancel_then_cleanup(terminate_execution())
