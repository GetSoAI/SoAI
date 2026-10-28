"""SoAI - Execution timeout attribution at the enforcing boundary [backend/orchestrator/execution/execution_phase_timeouts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from enum import StrEnum

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup, wait_for_task_completion
from core.concurrency.protocols import AsyncClosableIteratorProtocol
from core.concurrency.task_groups import cancel_and_await
from core.errors.backend_lifecycle import IpcCancellationCleanupError
from core.errors.error_types import ErrorType
from core.errors.exceptions import SoAITimeoutError, StateError
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import project_public_error
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.awaitable_cleanup import create_task_with_rejection_cleanup
from core.tasks.execution_budget import (
    ExecutionBudget,
    ExecutionBudgetSource,
    ExecutionLimit,
)
from core.tasks.execution_timeout_claim import claim_execution_timeout
from core.tasks.orchestration_context_cache import (
    is_current_execution_attempt,
    update_orchestration_context_from_current,
)
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from core.types.json import JSONDict
from orchestrator.execution.failure_classification_models import ExecutionFailureDetails
from orchestrator.execution.internal_protocols import ActiveInferenceRegistryProtocol

__all__ = (
    "ExecutionPhase",
    "ExecutionPhaseTimeout",
    "ExecutionPhaseTimeoutError",
    "admit_inference_execution_budget",
    "await_execution_phase",
    "await_within_execution_budget",
    "build_execution_phase_timeout_failure",
    "execution_phase_timeout_error",
)

LOGGER_NAME = "SoAI.orchestrator.execution.execution_phase_timeouts"


async def admit_inference_execution_budget(
    *,
    task_registry: TaskRegistryProtocol,
    active_inferences: ActiveInferenceRegistryProtocol,
    task: Task,
    limit: ExecutionLimit,
    health_check_config: JSONDict | None,
) -> tuple[Task, ExecutionBudget | None]:
    current_task = await update_orchestration_context_from_current(
        task_registry,
        task.task_id,
        lambda context: replace(
            context,
            execution_budget=(
                context.execution_budget
                if context.execution_budget is not None
                and context.execution_budget.generation == context.execution_generation
                else ExecutionBudget.start(
                    limit,
                    health_check_config=health_check_config,
                    generation=context.execution_generation,
                    previous=context.execution_budget,
                )
            ),
        ),
    )
    if current_task is None or current_task.status.is_terminal():
        return (current_task or task, None)
    context = current_task.orchestration_context
    if context is None or context.execution_budget is None:
        raise StateError("Inference execution budget was not established.")
    budget = context.execution_budget
    get_logger(LOGGER_NAME).debug(
        "Inference budget admitted. task_id=%s source=%s budget_seconds=%.3f deadline_monotonic=%.3f",
        task.task_id,
        budget.source.value,
        budget.budget_seconds,
        budget.deadline.deadline_monotonic,
    )
    await active_inferences.set_execution_limits(
        context.tracking_id,
        request_timeout=budget.budget_seconds,
        health_watchdog=limit.health_seconds,
        execution_budget=budget,
    )
    return (current_task, budget)


class ExecutionPhase(StrEnum):
    RESPONSE = "response"
    INITIAL_RESPONSE = "initial_response"
    FIRST_TOKEN = "first_token"
    BUFFERED_RESPONSE = "buffered_response"


@dataclass(frozen=True, slots=True)
class ExecutionPhaseTimeout:
    phase: ExecutionPhase
    budget_seconds: float
    elapsed_seconds: float
    cleanup_seconds: float
    source: ExecutionBudgetSource


class ExecutionPhaseTimeoutError(SoAITimeoutError):
    def __init__(self, attribution: ExecutionPhaseTimeout) -> None:
        super().__init__(
            (
                f"Execution phase '{attribution.phase.value}' exhausted its "
                f"{attribution.budget_seconds:.1f}s budget after "
                f"{attribution.elapsed_seconds:.1f}s; cleanup took "
                f"{attribution.cleanup_seconds:.1f}s."
            ),
            operation="orchestrator.execution_phase_timeout",
            details={
                "phase": attribution.phase.value,
                "budget_seconds": round(attribution.budget_seconds, 3),
                "elapsed_seconds": round(attribution.elapsed_seconds, 3),
                "cleanup_seconds": round(attribution.cleanup_seconds, 3),
                "budget_source": attribution.source.value,
            },
        )
        self.attribution = attribution


def execution_phase_timeout_error(
    budget: ExecutionBudget,
    phase: ExecutionPhase,
    *,
    wait_started_monotonic: float,
    limit_seconds: float,
    phase_cap: ExecutionLimit | None = None,
) -> ExecutionPhaseTimeoutError:
    enforced_at = wait_started_monotonic + max(0.0, limit_seconds)
    budget_seconds = budget.budget_seconds
    source = budget.source
    if phase_cap is not None and enforced_at < budget.deadline.deadline_monotonic:
        budget_seconds = phase_cap.seconds
        source = phase_cap.source
    return ExecutionPhaseTimeoutError(
        ExecutionPhaseTimeout(
            phase=phase,
            budget_seconds=budget_seconds,
            elapsed_seconds=max(0.0, enforced_at - budget.started_monotonic),
            cleanup_seconds=max(0.0, time.monotonic() - enforced_at),
            source=source,
        ),
    )


async def await_within_execution_budget[Result](
    awaitable: Awaitable[Result],
    *,
    budget: ExecutionBudget,
    phase: ExecutionPhase,
    task_registry: TaskRegistryProtocol | None = None,
    task: Task | None = None,
) -> Result:
    wait_started = time.monotonic()
    limit = budget.deadline.remaining_seconds()
    return await await_execution_phase(
        awaitable,
        timeout_seconds=limit,
        timeout_error=lambda: execution_phase_timeout_error(
            budget, phase, wait_started_monotonic=wait_started, limit_seconds=limit
        ),
        task_registry=task_registry,
        task=task,
    )


async def await_execution_phase[Result](
    awaitable: Awaitable[Result],
    *,
    timeout_seconds: float,
    timeout_error: Callable[[], SoAITimeoutError],
    task_registry: TaskRegistryProtocol | None,
    task: Task | None,
) -> Result:
    worker = create_task_with_rejection_cleanup(awaitable, name="inference.execution_phase")
    completed = False
    attempt_can_failover = False
    try:
        done: set[asyncio.Task[Result]] = set()
        if timeout_seconds > 0:
            done, _pending = await asyncio.wait((worker,), timeout=timeout_seconds)
        current_task = (
            await task_registry.get(task.task_id)
            if task_registry is not None and task is not None
            else None
        )
        if (
            task is not None
            and task_registry is not None
            and (
                not is_current_execution_attempt(task, current_task)
                or current_task is None
                or current_task.status.is_terminal()
            )
        ):
            raise asyncio.CancelledError()
        if done:
            completed = True
            return worker.result()
        exception = timeout_error()
        if task_registry is not None and task is not None:
            context = current_task.orchestration_context if current_task is not None else None
            attempt_can_failover = (
                isinstance(exception, ExecutionPhaseTimeoutError)
                and exception.attribution.source is ExecutionBudgetSource.PLUGIN_HEALTH
                and context is not None
                and context.virtual_model_name is not None
                and len(context.execution_universal_ids) > 1
                and not context.delivery_in_progress
                and not context.streaming_started
            )
            public_error = (
                build_execution_phase_timeout_failure(task.task_id, exception).public_error
                if isinstance(exception, ExecutionPhaseTimeoutError)
                else project_public_error(exception)
            )
            if public_error is None:
                raise StateError("Execution timeout requires public failure guidance.")
            if not attempt_can_failover:
                claimed = await uncancel_then_cleanup(
                    claim_execution_timeout(task_registry, task.task_id, public_error)
                )
                if not claimed:
                    raise asyncio.CancelledError()
        raise exception
    finally:
        await uncancel_then_cleanup(cancel_and_await((worker,), timeout_sec=RESPONSIVE_TIMEOUT_SEC))
        await wait_for_task_completion(worker, retain_resources_until_complete=True)
        if not worker.cancelled():
            cleanup_error = worker.exception()
            if attempt_can_failover and cleanup_error is not None:
                raise _timeout_cleanup_failure(cleanup_error)
            if cleanup_error is None:
                result = worker.result()
                if isinstance(result, AsyncClosableIteratorProtocol) and not completed:
                    try:
                        await uncancel_then_cleanup(result.aclose())
                    except HANDLED_RUNTIME_EXCEPTIONS as close_error:
                        if attempt_can_failover and not isinstance(
                            close_error, IpcCancellationCleanupError
                        ):
                            raise _timeout_cleanup_failure(close_error) from close_error
                        raise


def _timeout_cleanup_failure(exception: BaseException) -> IpcCancellationCleanupError:
    if isinstance(exception, IpcCancellationCleanupError):
        return exception
    return IpcCancellationCleanupError(
        "Inference timeout cleanup did not confirm termination.", cause=exception
    )


def build_execution_phase_timeout_failure(
    task_id: str,
    exception: ExecutionPhaseTimeoutError,
) -> ExecutionFailureDetails:
    attribution = exception.attribution
    caller_owned = attribution.source is ExecutionBudgetSource.CALLER_REQUEST
    budget_label = "the request's" if caller_owned else "its"
    budget_kind = "time limit" if caller_owned else "execution budget"
    user_message = (
        f"{_phase_user_message(attribution.phase)} within {budget_label} "
        f"{attribution.budget_seconds:.1f}s {budget_kind} "
        f"({attribution.elapsed_seconds:.1f}s elapsed)."
    )
    return ExecutionFailureDetails(
        user_message=user_message,
        state_reason=(
            f"Task {task_id} failed: {attribution.phase.value} timeout "
            f"(owner {attribution.source.value}, budget {attribution.budget_seconds:.1f}s, "
            f"elapsed {attribution.elapsed_seconds:.1f}s, "
            f"cleanup {attribution.cleanup_seconds:.1f}s)"
        ),
        log_stack=False,
        error_type=ErrorType.TIMEOUT_ERROR,
        affects_plugin_health=not caller_owned,
        allow_failover=not caller_owned,
        public_error=ErrorPublicPayload(
            code=ErrorType.TIMEOUT_ERROR.value,
            message=user_message,
            details={
                "phase": attribution.phase.value,
                "budget_seconds": round(attribution.budget_seconds, 3),
                "elapsed_seconds": round(attribution.elapsed_seconds, 3),
                "cleanup_seconds": round(attribution.cleanup_seconds, 3),
                "budget_source": attribution.source.value,
            },
            http_status=SoAITimeoutError.http_status,
        ),
    )


def _phase_user_message(phase: ExecutionPhase) -> str:
    match phase:
        case ExecutionPhase.RESPONSE:
            return "The plugin did not return a response"
        case ExecutionPhase.INITIAL_RESPONSE:
            return "The model did not begin responding"
        case ExecutionPhase.FIRST_TOKEN:
            return "The model did not produce its first output"
        case ExecutionPhase.BUFFERED_RESPONSE:
            return "The model did not finish its response"
