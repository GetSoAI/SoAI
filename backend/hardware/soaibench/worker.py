"""SoAI - SoAIBench worker lifecycle [backend/hardware/soaibench/worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError, SoAITimeoutError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from hardware.soaibench.errors import SoAIBenchHeartbeatSuperseded, SoAIBenchUnsupported
from hardware.soaibench.events import publish_soaibench_worker_update
from hardware.soaibench.preflight import run_preflight
from hardware.soaibench.start_state import persist_preflight_summary
from hardware.soaibench.telemetry import SoAIBenchTelemetryDiagnostics
from hardware.soaibench.worker_cancellation import (
    finish_direct_cancellation_preserving,
)
from hardware.soaibench.worker_context import (
    SoAIBenchWorkerEventContext,
    SoAIBenchWorkerRuntimeContext,
    SoAIBenchWorkerState,
)
from hardware.soaibench.worker_inputs import (
    base_summary_from_run,
    parse_worker_run_inputs,
)
from hardware.soaibench.worker_profiles import run_selected_profile
from hardware.soaibench.worker_runtime_conditions import finish_cancelled_runtime_profile
from hardware.soaibench.worker_settlement import (
    close_execution_or_fail,
    settle_execution_failure,
    settle_soaibench_terminal,
)
from hardware.soaibench.worker_terminal import (
    finish_failure,
    finish_unstable,
    finish_unsupported,
)

if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.events.protocols import EventBusProtocol
    from core.hardware.protocols import HardwareManagerProtocol
    from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallActivity
    from core.types.json import JSONDict
    from hardware.soaibench.internal_protocols import SoAIBenchOpenCLExecutionProtocol
    from hardware.soaibench.types import SoAIBenchGpuIdentity

__all__ = ("run_soaibench_worker",)

UNSTABLE_FAILURE_REASONS: tuple[str, ...] = (
    "opencl_checksum_failed",
    "opencl_device_lost",
    "opencl_numerical_mismatch",
)
WORKER_OPERATION = "hardware.soaibench.worker"


async def run_soaibench_worker(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    event_bus: EventBusProtocol,
    logger: LoggerProtocol,
    hardware_manager: HardwareManagerProtocol,
    telemetry_pool: BoundedBlockingPool,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    run: JSONDict,
    identity: SoAIBenchGpuIdentity,
    task_registry: TaskRegistryProtocol,
    run_id: str,
    task_id: str,
    stop_event: asyncio.Event,
    deferred_tool_activity: DeferredToolCallActivity | None,
) -> None:
    run_inputs = parse_worker_run_inputs(run)
    event_context = SoAIBenchWorkerEventContext(
        event_bus=event_bus,
        logger=logger,
        task_id=task_id,
    )
    worker_state = SoAIBenchWorkerState(current_run=run)
    runtime_context = SoAIBenchWorkerRuntimeContext(
        database_hardware=database_hardware,
        hardware_manager=hardware_manager,
        logger=logger,
        task_registry=task_registry,
        run_id=run_id,
        task_id=task_id,
        identity=identity,
        started_at_ms=run_inputs.started_at_ms,
        base_summary=run_inputs.base_summary,
        settings_snapshot=run_inputs.settings_snapshot,
        temperature_limit_celsius=run_inputs.temperature_limit_celsius,
        stop_event=stop_event,
        telemetry_diagnostics=SoAIBenchTelemetryDiagnostics(blocking_pool=telemetry_pool),
        state=worker_state,
    )
    try:
        if stop_event.is_set():
            await opencl_pool.close()
            terminal = await finish_cancelled_runtime_profile(
                runtime_context=runtime_context,
                profile=run_inputs.profile,
            )
            await settle_soaibench_terminal(
                event_context=event_context,
                task_registry=task_registry,
                deferred_tool_activity=deferred_tool_activity,
                run=terminal,
            )
            return
        match = await run_preflight(opencl_pool=opencl_pool, identity=identity)
        preflight_run = await persist_preflight_summary(
            database_hardware=database_hardware,
            run=run,
            match=match,
        )
        worker_state.current_run = preflight_run
        run_inputs.base_summary.clear()
        run_inputs.base_summary.update(base_summary_from_run(preflight_run))
        await publish_soaibench_worker_update(event_context, preflight_run, "preflight")
        await run_selected_profile(
            opencl_pool=opencl_pool,
            runtime_context=runtime_context,
            event_context=event_context,
            profile=run_inputs.profile,
            benchmark_mode=run_inputs.benchmark_mode,
        )
        if worker_state.terminal_run is not None:
            await settle_soaibench_terminal(
                event_context=event_context,
                task_registry=task_registry,
                deferred_tool_activity=deferred_tool_activity,
                run=worker_state.terminal_run,
            )
    except asyncio.CancelledError as exception:
        try:
            await uncancel_then_cleanup(opencl_pool.close())
        except ProcessError as cleanup_exception:
            if opencl_pool.degraded:
                terminal = await finish_failure(
                    database_hardware=database_hardware,
                    run_id=run_id,
                    started_at_ms=run_inputs.started_at_ms,
                    base_summary=run_inputs.base_summary,
                    reason="opencl_child_termination_failed",
                    message="SoAI Bench OpenCL child termination could not be verified.",
                )
                await settle_soaibench_terminal(
                    event_context=event_context,
                    task_registry=task_registry,
                    deferred_tool_activity=deferred_tool_activity,
                    run=terminal,
                )
                raise
            exception.add_note(
                f"SoAI Bench OpenCL child exited during cancellation: {cleanup_exception}"
            )
        await finish_direct_cancellation_preserving(
            runtime_context=runtime_context,
            profile=run_inputs.profile,
            primary_exception=exception,
        )
        if worker_state.terminal_run is not None:
            await settle_soaibench_terminal(
                event_context=event_context,
                task_registry=task_registry,
                deferred_tool_activity=deferred_tool_activity,
                run=worker_state.terminal_run,
            )
        raise
    except (ProcessError, SoAITimeoutError) as exception:
        await uncancel_then_cleanup(
            settle_execution_failure(
                opencl_pool=opencl_pool,
                exception=exception,
                runtime_context=runtime_context,
                event_context=event_context,
                deferred_tool_activity=deferred_tool_activity,
            )
        )
    except SoAIBenchHeartbeatSuperseded as exception:
        if exception.durable_run.get("status") == "running":
            await stop_event.wait()
        if not await close_execution_or_fail(
            opencl_pool=opencl_pool,
            primary_exception=exception,
            runtime_context=runtime_context,
            event_context=event_context,
            deferred_tool_activity=deferred_tool_activity,
        ):
            return
        terminal = await finish_cancelled_runtime_profile(
            runtime_context=runtime_context,
            profile=run_inputs.profile,
        )
        await settle_soaibench_terminal(
            event_context=event_context,
            task_registry=task_registry,
            deferred_tool_activity=deferred_tool_activity,
            run=terminal,
        )
    except SoAIBenchUnsupported as exception:
        if not await close_execution_or_fail(
            opencl_pool=opencl_pool,
            primary_exception=exception,
            runtime_context=runtime_context,
            event_context=event_context,
            deferred_tool_activity=deferred_tool_activity,
        ):
            return
        if exception.reason in UNSTABLE_FAILURE_REASONS:
            terminal = await finish_unstable(
                database_hardware=database_hardware,
                run_id=run_id,
                started_at_ms=run_inputs.started_at_ms,
                base_summary=base_summary_from_run(worker_state.current_run),
                reason=exception.reason,
                message=exception.message,
            )
            await settle_soaibench_terminal(
                event_context=event_context,
                task_registry=task_registry,
                deferred_tool_activity=deferred_tool_activity,
                run=terminal,
            )
            return
        terminal = await finish_unsupported(
            database_hardware=database_hardware,
            run_id=run_id,
            started_at_ms=run_inputs.started_at_ms,
            base_summary=base_summary_from_run(worker_state.current_run),
            exception=exception,
        )
        await settle_soaibench_terminal(
            event_context=event_context,
            task_registry=task_registry,
            deferred_tool_activity=deferred_tool_activity,
            run=terminal,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        if not await close_execution_or_fail(
            opencl_pool=opencl_pool,
            primary_exception=exception,
            runtime_context=runtime_context,
            event_context=event_context,
            deferred_tool_activity=deferred_tool_activity,
        ):
            return
        log_exception(
            logger,
            exception,
            message="SoAI Bench recoverable worker failure.",
            operation=WORKER_OPERATION,
        )
        terminal = await finish_failure(
            database_hardware=database_hardware,
            run_id=run_id,
            started_at_ms=run_inputs.started_at_ms,
            base_summary=base_summary_from_run(worker_state.current_run),
            reason="opencl_runtime_error",
            message="SoAI Bench failed while executing the OpenCL workload.",
        )
        await settle_soaibench_terminal(
            event_context=event_context,
            task_registry=task_registry,
            deferred_tool_activity=deferred_tool_activity,
            run=terminal,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        if not await close_execution_or_fail(
            opencl_pool=opencl_pool,
            primary_exception=exception,
            runtime_context=runtime_context,
            event_context=event_context,
            deferred_tool_activity=deferred_tool_activity,
        ):
            return
        coerced_exception = coerce_to_soai_error(
            exception,
            operation=WORKER_OPERATION,
        )
        log_exception(
            logger,
            coerced_exception,
            message="SoAI Bench worker failure.",
            operation=WORKER_OPERATION,
        )
        terminal = await finish_failure(
            database_hardware=database_hardware,
            run_id=run_id,
            started_at_ms=run_inputs.started_at_ms,
            base_summary=base_summary_from_run(worker_state.current_run),
            reason="opencl_runtime_error",
            message="SoAI Bench failed while executing the OpenCL workload.",
        )
        await settle_soaibench_terminal(
            event_context=event_context,
            task_registry=task_registry,
            deferred_tool_activity=deferred_tool_activity,
            run=terminal,
        )
