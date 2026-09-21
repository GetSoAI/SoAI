"""SoAI - SoAIBench worker runtime condition handling [backend/hardware/soaibench/worker_runtime_conditions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from core.tasks.status_transitions import update_progress
from core.timing.epoch import epoch_ms
from hardware.soaibench.events import publish_soaibench_worker_update
from hardware.soaibench.start_state import materialized_heartbeat_run
from hardware.soaibench.telemetry import read_soaibench_telemetry_snapshot
from hardware.soaibench.types import SoAIBenchProfile
from hardware.soaibench.worker_terminal import finish_cancelled, finish_unstable

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.soaibench.telemetry import (
        SoAIBenchTelemetryAccumulator,
        SoAIBenchTelemetrySnapshot,
    )
    from hardware.soaibench.worker_context import (
        SoAIBenchWorkerEventContext,
        SoAIBenchWorkerRuntimeContext,
    )

__all__ = (
    "finish_cancelled_if_stopped",
    "finish_cancelled_runtime_profile",
    "finish_unstable_for_telemetry",
    "persist_worker_heartbeat",
    "read_worker_telemetry",
    "read_telemetry_or_finish_unstable",
)


async def read_telemetry_or_finish_unstable(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    telemetry_accumulator: SoAIBenchTelemetryAccumulator,
    terminate_execution: Callable[[], Awaitable[None]],
) -> SoAIBenchTelemetrySnapshot | None:
    telemetry = await read_worker_telemetry(
        runtime_context=runtime_context,
        accumulator=telemetry_accumulator,
    )
    if not telemetry.temperature_exceeded:
        return telemetry
    await finish_unstable_for_telemetry(
        runtime_context=runtime_context,
        telemetry_accumulator=telemetry_accumulator,
        telemetry=telemetry,
        terminate_execution=terminate_execution,
    )
    return None


async def finish_unstable_for_telemetry(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    telemetry_accumulator: SoAIBenchTelemetryAccumulator,
    telemetry: SoAIBenchTelemetrySnapshot,
    terminate_execution: Callable[[], Awaitable[None]],
) -> JSONDict:
    await terminate_execution()
    terminal_run = await finish_unstable(
        database_hardware=runtime_context.database_hardware,
        run_id=runtime_context.run_id,
        started_at_ms=runtime_context.started_at_ms,
        base_summary={**runtime_context.base_summary, **telemetry_accumulator.summary()},
        reason=telemetry.instability_reason or "temperature_limit_exceeded",
        message=telemetry.instability_message or "GPU temperature limit exceeded.",
    )
    runtime_context.state.current_run = terminal_run
    runtime_context.state.terminal_run = terminal_run
    return terminal_run


async def read_worker_telemetry(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    accumulator: SoAIBenchTelemetryAccumulator,
) -> SoAIBenchTelemetrySnapshot:
    telemetry = await read_soaibench_telemetry_snapshot(
        runtime_context.hardware_manager,
        device_id=runtime_context.identity.device_id,
        temperature_limit_celsius=runtime_context.temperature_limit_celsius,
        logger=runtime_context.logger,
        diagnostics=runtime_context.telemetry_diagnostics,
    )
    accumulator.add(telemetry)
    return telemetry


async def persist_worker_heartbeat(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    event_context: SoAIBenchWorkerEventContext,
    summary: JSONDict,
    sample_count: int,
    progress_current: int,
    status_message: str,
) -> None:
    heartbeat = await runtime_context.database_hardware.update_soaibench_heartbeat(
        run_id=runtime_context.run_id,
        last_heartbeat_at_ms=epoch_ms(),
        sample_count=sample_count,
        summary_json=serialize_json_compact_stable(summary),
    )
    heartbeat_run = materialized_heartbeat_run(heartbeat)
    runtime_context.state.current_run = heartbeat_run
    await publish_soaibench_worker_update(event_context, heartbeat_run, "heartbeat")
    await update_progress(
        runtime_context.task_registry,
        runtime_context.task_id,
        progress_current,
        status_message=status_message,
    )


async def finish_cancelled_if_stopped(
    *,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    base_summary: JSONDict | None = None,
    terminate_execution: Callable[[], Awaitable[None]],
) -> bool:
    if not runtime_context.stop_event.is_set():
        return False
    await terminate_execution()
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
) -> JSONDict:
    terminal_run = await finish_cancelled(
        database_hardware=runtime_context.database_hardware,
        run_id=runtime_context.run_id,
        started_at_ms=runtime_context.started_at_ms,
        base_summary=base_summary or runtime_context.base_summary,
        profile=profile,
        stop_event=runtime_context.stop_event,
    )
    runtime_context.state.current_run = terminal_run
    runtime_context.state.terminal_run = terminal_run
    return terminal_run
