"""SoAI - SoAIBench terminal companion settlement [backend/hardware/soaibench/worker_settlement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError, SoAITimeoutError
from core.system.native_runtime_probes import RuntimeStartupTimeoutError
from hardware.soaibench.errors import (
    SoAIBenchCompanionFinalizationError,
    execution_failure_projection,
)
from hardware.soaibench.terminal_companions import finalize_soaibench_terminal_companions
from hardware.soaibench.worker_inputs import base_summary_from_run
from hardware.soaibench.worker_terminal import finish_failure

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallActivity
    from core.types.json import JSONDict
    from hardware.soaibench.internal_protocols import SoAIBenchOpenCLExecutionProtocol
    from hardware.soaibench.worker_context import (
        SoAIBenchWorkerEventContext,
        SoAIBenchWorkerRuntimeContext,
    )

__all__ = ("close_execution_or_fail", "settle_execution_failure", "settle_soaibench_terminal")

WORKER_OPERATION = "hardware.soaibench.worker"


async def settle_execution_failure(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    exception: ProcessError | SoAITimeoutError,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    event_context: SoAIBenchWorkerEventContext,
    deferred_tool_activity: DeferredToolCallActivity | None,
) -> None:
    cleanup_verified = await close_execution_or_fail(
        opencl_pool=opencl_pool,
        primary_exception=exception,
        runtime_context=runtime_context,
        event_context=event_context,
        deferred_tool_activity=deferred_tool_activity,
    )
    if not cleanup_verified:
        return
    failure = execution_failure_projection(exception)
    terminal = await finish_failure(
        database_hardware=runtime_context.database_hardware,
        run_id=runtime_context.run_id,
        started_at_ms=runtime_context.started_at_ms,
        base_summary={
            **base_summary_from_run(runtime_context.state.current_run),
            **failure.summary,
        },
        reason=failure.reason,
        message=failure.message,
    )
    runtime_context.state.current_run = terminal
    runtime_context.state.terminal_run = terminal
    await settle_soaibench_terminal(
        event_context=event_context,
        task_registry=runtime_context.task_registry,
        deferred_tool_activity=deferred_tool_activity,
        run=terminal,
    )
    if terminal.get("failure_reason") == failure.reason:
        log_exception(
            runtime_context.logger,
            exception,
            message=failure.message,
            operation=WORKER_OPERATION,
            level=(
                "warning"
                if isinstance(exception, SoAITimeoutError | RuntimeStartupTimeoutError)
                else "error"
            ),
            details={"task_id": runtime_context.task_id, "run_id": runtime_context.run_id},
        )


async def close_execution_or_fail(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    primary_exception: BaseException,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    event_context: SoAIBenchWorkerEventContext,
    deferred_tool_activity: DeferredToolCallActivity | None,
) -> bool:
    try:
        await opencl_pool.close()
    except ProcessError as cleanup_exception:
        if not opencl_pool.degraded:
            if isinstance(primary_exception, ProcessError | SoAITimeoutError) and (
                (cleanup_exception.details or {}).get("return_code") is not None
            ):
                details = primary_exception.details or {}
                details["unexpected_exit_code"] = (cleanup_exception.details or {}).get(
                    "return_code"
                )
                if details.get("failure_type") in (None, "disconnected"):
                    details["failure_type"] = "child_exit"
                primary_exception.details = details
            primary_exception.add_note(
                f"SoAI Bench OpenCL child exited during cleanup: {cleanup_exception}"
            )
            return True
        log_exception(
            runtime_context.logger,
            cleanup_exception,
            message="SoAI Bench owned OpenCL cleanup remains unverified.",
            operation=WORKER_OPERATION,
            level="warning",
            details={
                **(cleanup_exception.details or {}),
                "task_id": runtime_context.task_id,
                "run_id": runtime_context.run_id,
            },
        )
        terminal = await finish_failure(
            database_hardware=runtime_context.database_hardware,
            run_id=runtime_context.run_id,
            started_at_ms=runtime_context.started_at_ms,
            base_summary=base_summary_from_run(runtime_context.state.current_run),
            reason="opencl_child_termination_failed",
            message="SoAI Bench OpenCL child termination could not be verified.",
        )
        runtime_context.state.current_run = terminal
        runtime_context.state.terminal_run = terminal
        await settle_soaibench_terminal(
            event_context=event_context,
            task_registry=runtime_context.task_registry,
            deferred_tool_activity=deferred_tool_activity,
            run=terminal,
        )
        return False
    return True


async def settle_soaibench_terminal(
    *,
    event_context: SoAIBenchWorkerEventContext,
    task_registry: TaskRegistryProtocol,
    deferred_tool_activity: DeferredToolCallActivity | None,
    run: JSONDict,
) -> None:
    try:
        await finalize_soaibench_terminal_companions(
            event_context=event_context,
            task_registry=task_registry,
            deferred_tool_activity=deferred_tool_activity,
            run=run,
        )
    except SoAIBenchCompanionFinalizationError as exception:
        for failure in exception.failures:
            log_exception(
                event_context.logger,
                failure.exception,
                message="SoAI Bench durable companion finalization failed.",
                operation=WORKER_OPERATION,
                details={
                    "run_id": str(run["run_id"]),
                    "companion": failure.code,
                },
            )
