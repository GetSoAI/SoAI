"""SoAI - SoAIBench phase execution with active telemetry sampling [backend/hardware/soaibench/phase_telemetry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
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
            raise StateError("SoAI Bench phase result is unavailable after interruption.")
        return self.phase_result


async def run_phase_with_telemetry(
    *,
    awaitable: Coroutine[None, None, SoAIBenchPhaseResult],
    task_name: str,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    telemetry_accumulator: SoAIBenchTelemetryAccumulator,
    sample_interval_seconds: float,
    terminate_execution: Callable[[], Awaitable[None]] | None = None,
    pass_telemetry_accumulator: SoAIBenchTelemetryAccumulator | None = None,
) -> PhaseTelemetryRunResult:
    phase_task = create_ephemeral_task(awaitable, name=task_name, log_exceptions=False)
    terminal_telemetry: SoAIBenchTelemetrySnapshot | None = None
    phase_observed_active = False
    interrupted = False
    telemetry_task: asyncio.Task[SoAIBenchTelemetrySnapshot] | None = None
    stop_task = create_ephemeral_task(
        runtime_context.stop_event.wait(), name=f"{task_name}-stop", log_exceptions=False
    )
    try:
        while not phase_task.done():
            if runtime_context.stop_event.is_set():
                interrupted = True
                break
            carried_read = runtime_context.state.telemetry_read_task is not None
            telemetry_task = create_ephemeral_task(
                read_worker_telemetry(
                    runtime_context=runtime_context,
                    accumulator=telemetry_accumulator,
                ),
                name=f"{task_name}-telemetry",
                log_exceptions=False,
            )
            while not telemetry_task.done() and not phase_task.done() and not stop_task.done():
                completed, _pending = await asyncio.wait(
                    (phase_task, telemetry_task, stop_task),
                    timeout=sample_interval_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not completed:
                    phase_observed_active = True
            if stop_task.done():
                interrupted = True
                break
            if not telemetry_task.done():
                break
            telemetry = await telemetry_task
            if (
                pass_telemetry_accumulator is not None
                and phase_observed_active
                and not carried_read
                and not phase_task.done()
            ):
                pass_telemetry_accumulator.add(telemetry)
            if telemetry.temperature_exceeded:
                terminal_telemetry = telemetry
                interrupted = True
                break
            if phase_task.done():
                break
            completed, _pending = await asyncio.wait(
                (phase_task, stop_task),
                timeout=sample_interval_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_task in completed:
                interrupted = True
                break
            phase_observed_active = not phase_task.done()
    finally:
        await uncancel_then_cleanup(
            cancel_and_await((telemetry_task, stop_task), task_label=f"{task_name} telemetry")
        )
        if not phase_task.done():
            try:
                await uncancel_then_cleanup(cancel_and_await((phase_task,), task_label=task_name))
            finally:
                if terminate_execution is not None:
                    await uncancel_then_cleanup(terminate_execution())
        elif not phase_task.cancelled():
            phase_exception = phase_task.exception()
            if phase_exception is not None and sys.exception() is None:
                raise phase_exception
    if telemetry_task is not None and not telemetry_task.cancelled():
        telemetry = telemetry_task.result()
        if telemetry.temperature_exceeded:
            terminal_telemetry = telemetry
            interrupted = True
    return PhaseTelemetryRunResult(
        phase_result=None if interrupted else phase_task.result(),
        terminal_telemetry=terminal_telemetry,
    )
