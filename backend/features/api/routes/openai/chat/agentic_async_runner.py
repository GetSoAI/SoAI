"""SoAI - Async agentic coordinator task execution [backend/features/api/routes/openai/chat/agentic_async_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.runtime.request_context import RequestContext
from core.tasks.enums import TaskStatus
from core.tasks.errors import TASK_STATE_PERSISTENCE_FAILED_MESSAGE
from core.tasks.finalization import finalize
from core.tasks.status_transitions import update_status
from features.api.routes.openai.chat.agentic_dispatch_support import (
    AgenticExecutionInputs,
    build_agentic_prepared_execution_request_from_inputs,
    execute_prepared_agentic_non_streaming,
)
from features.api.routes.openai.chat.inference_request_failure_handling import (
    finalize_openai_running_turn_error_noncritical,
    finalize_openai_running_turn_noncritical,
)

if TYPE_CHECKING:
    from core.orchestrator.types import MCPToolContext
    from features.api.runtime.context import ApiContext

__all__ = ("run_agentic_async_coordinator_task",)

OPERATION = "api_openai.agentic_async.execute"
_EXPECTED_AGENT_FAILURES = (*RECOVERABLE_EXCEPTIONS, SoAIError)


async def run_agentic_async_coordinator_task(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    execution_inputs: AgenticExecutionInputs,
    timeout_value: float,
    coordinator_task_id: str,
) -> None:
    context = execution_inputs.context
    tool_context = execution_inputs.tool_context
    try:
        working_task = await update_status(
            api_context.dependencies.task_registry,
            coordinator_task_id,
            TaskStatus.WORKING,
            status_message="Running agent turn",
        )
        if working_task is None:
            current_task = await api_context.dependencies.task_registry.get(coordinator_task_id)
            if current_task is None or current_task.status.is_terminal():
                return
            await _finalize_agentic_async_failure(
                api_context=api_context,
                logger=logger,
                context=context,
                tool_context=tool_context,
                coordinator_task_id=coordinator_task_id,
                error_message=TASK_STATE_PERSISTENCE_FAILED_MESSAGE,
                error_type="task_state_persistence_failed",
                error_status=500,
                turn_cleanup_message="Failed to finalize async agent turn after task state persistence failure.",
            )
            return
        execution_request = build_agentic_prepared_execution_request_from_inputs(
            inputs=execution_inputs,
            timeout_value=timeout_value,
        )
        execution = await execute_prepared_agentic_non_streaming(
            execution_request=execution_request,
            event_type_label="agentic_async",
        )
        completed_task = await finalize(
            api_context.dependencies.task_registry,
            coordinator_task_id,
            TaskStatus.COMPLETED,
            result=execution.result.final_payload,
            status_message="Completed",
        )
        if completed_task is None:
            raise StateError("Accepted agent task did not reach completed state.")
        if completed_task.status != TaskStatus.COMPLETED:
            return
    except asyncio.CancelledError:
        await finalize_openai_running_turn_noncritical(
            api_context=api_context,
            logger=logger,
            context=context,
            tool_context=tool_context,
            status="cancelled",
            reached_max_iterations=False,
            error_message="Agent turn cancelled.",
            error_type="cancelled",
            operation="api_openai.agentic_async.turn_cleanup",
            log_message="Failed to finalize async accepted agent turn after coordinator cancellation (non-critical).",
        )
        await finalize(
            api_context.dependencies.task_registry,
            coordinator_task_id,
            TaskStatus.CANCELLED,
            error_message="Agent turn cancelled.",
            status_message="Agent turn cancelled.",
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="api_openai.agentic_async.execute",
        )
        log_exception(
            logger,
            coerced,
            message="Async accepted agentic request failed.",
            trace_id=context.trace_id,
            operation=OPERATION,
            level="error",
            details={
                "conv_id": tool_context.conv_id,
                "task_id": coordinator_task_id,
                "turn_id": context.agent_turn_id,
            },
        )
        unexpected = not isinstance(exception, _EXPECTED_AGENT_FAILURES)
        await _finalize_agentic_async_failure(
            api_context=api_context,
            logger=logger,
            context=context,
            tool_context=tool_context,
            coordinator_task_id=coordinator_task_id,
            error_message=("Internal server error." if unexpected else coerced.message),
            error_type=("server_error" if unexpected else str(coerced.code)),
            error_status=(500 if unexpected else coerced.http_status),
            turn_cleanup_message="Failed to finalize async accepted agent turn after coordinator error (non-critical).",
        )


async def _finalize_agentic_async_failure(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    context: RequestContext,
    tool_context: MCPToolContext,
    coordinator_task_id: str,
    error_message: str,
    error_type: str,
    error_status: int,
    turn_cleanup_message: str,
) -> None:
    await finalize_openai_running_turn_error_noncritical(
        api_context=api_context,
        logger=logger,
        context=context,
        tool_context=tool_context,
        error_message=error_message,
        error_type=error_type,
        operation="api_openai.agentic_async.turn_cleanup",
        log_message=turn_cleanup_message,
    )
    await finalize(
        api_context.dependencies.task_registry,
        coordinator_task_id,
        TaskStatus.FAILED,
        error_code=error_status,
        error_message=error_message,
        status_message=error_message,
    )
