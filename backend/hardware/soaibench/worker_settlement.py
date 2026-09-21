"""SoAI - SoAIBench terminal companion settlement [backend/hardware/soaibench/worker_settlement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError
from hardware.soaibench.errors import SoAIBenchCompanionFinalizationError
from hardware.soaibench.terminal_companions import finalize_soaibench_terminal_companions
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

__all__ = ("close_execution_or_fail", "settle_soaibench_terminal")

WORKER_OPERATION = "hardware.soaibench.worker"


async def close_execution_or_fail(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    runtime_context: SoAIBenchWorkerRuntimeContext,
    event_context: SoAIBenchWorkerEventContext,
    deferred_tool_activity: DeferredToolCallActivity | None,
) -> bool:
    try:
        await opencl_pool.close()
    except ProcessError:
        terminal = await finish_failure(
            database_hardware=runtime_context.database_hardware,
            run_id=runtime_context.run_id,
            started_at_ms=runtime_context.started_at_ms,
            base_summary=runtime_context.base_summary,
            reason="opencl_child_termination_failed",
            message="SoAIBench OpenCL child termination could not be verified.",
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
                message="SoAIBench durable companion finalization failed.",
                operation=WORKER_OPERATION,
                details={
                    "run_id": str(run["run_id"]),
                    "companion": failure.code,
                },
            )
