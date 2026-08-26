"""SoAI - Automation execution validation and failure handling [backend/features/automation/execution_failure_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.automation.automation_constants import AUTOMATION_TIMEOUT_REASON_PREFIX
from core.automation.automation_identifiers import build_automation_run_cancellation_id
from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from features.automation.execution_failure_logging import log_automation_run_failure
from features.automation.run_terminal_transitions import (
    complete_automation_run_terminal,
    finalize_automation_run_task_terminal,
    resolve_failure_terminal_status,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "coerce_automation_error_message",
    "handle_automation_run_failure",
)


def coerce_automation_error_message(exception: BaseException) -> str:
    coerced = exception
    if not isinstance(coerced, SoAIError):
        coerced = coerce_to_soai_error(
            exception,
            operation="automation.executor.execute",
        )
    message_value = coerced.message if isinstance(coerced, SoAIError) else ""
    message = message_value.strip() if isinstance(message_value, str) else ""
    return message[:500] if message else "Automation execution failed."


def _extract_timeout_reason(exception: BaseException) -> str | None:
    candidates: list[BaseException] = [exception]
    if isinstance(exception, SoAIError) and isinstance(exception.cause, BaseException):
        candidates.append(exception.cause)
    for candidate in candidates:
        if isinstance(candidate, TaskCancelledError):
            reason = str(candidate.reason or "").strip()
            if reason.lower().startswith(AUTOMATION_TIMEOUT_REASON_PREFIX):
                return reason[:500] if reason else None
        if isinstance(candidate, asyncio.CancelledError):
            continue
    return None


async def _resolve_timeout_reason_from_cancellation_history(
    api_dependencies: ApiDependencies,
    *,
    logger: LoggerProtocol,
    operation: str,
    run_id: str,
    automation_id: str,
) -> str | None:
    cancellation_id = build_automation_run_cancellation_id(run_id)
    try:
        reason_value = await api_dependencies.cancellation_history.get_reason(cancellation_id)
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            logger,
            coerced,
            message="Failed to resolve automation timeout reason from cancellation history.",
            operation=operation,
            level="warning",
            details={"run_id": run_id, "automation_id": automation_id},
        )
        return None
    reason = (
        reason_value.strip() if isinstance(reason_value, str) and reason_value.strip() else None
    )
    if reason is None:
        return None
    if reason.lower().startswith(AUTOMATION_TIMEOUT_REASON_PREFIX):
        return reason[:500]
    return None


async def handle_automation_run_failure(
    api_dependencies: ApiDependencies,
    *,
    logger: LoggerProtocol,
    operation: str,
    run_id: str,
    automation_id: str,
    user_id: int | None,
    owner_task_id: str | None,
    latest_excerpt: str | None,
    exception: BaseException,
    run_completed_recorded: bool,
) -> None:
    cause_exception = exception.cause if isinstance(exception, SoAIError) else None
    is_cancelled = isinstance(exception, TaskCancelledError | asyncio.CancelledError) or isinstance(
        cause_exception,
        TaskCancelledError | asyncio.CancelledError,
    )
    timeout_reason = _extract_timeout_reason(exception)
    if timeout_reason is None and is_cancelled:
        timeout_reason = await _resolve_timeout_reason_from_cancellation_history(
            api_dependencies,
            logger=logger,
            operation=operation,
            run_id=run_id,
            automation_id=automation_id,
        )
    is_timeout = timeout_reason is not None
    coerced = coerce_to_soai_error(
        exception,
        operation="automation.executor.execute",
        details={"run_id": run_id, "automation_id": automation_id},
    )
    error_message = timeout_reason or coerce_automation_error_message(coerced)
    log_message = (
        "Automation run execution timed out."
        if is_timeout
        else (
            "Automation run execution was cancelled."
            if is_cancelled
            else "Automation run execution failed."
        )
    )
    log_automation_run_failure(
        logger,
        coerced,
        message=log_message,
        operation=operation,
        run_id=run_id,
        automation_id=automation_id,
        is_timeout=is_timeout,
        is_cancelled=is_cancelled,
    )
    if run_completed_recorded:
        return
    run_error_recorded = False
    final_status = resolve_failure_terminal_status(
        is_timeout=is_timeout,
        is_cancelled=is_cancelled,
    )
    if user_id is not None:
        try:
            completed_run = await complete_automation_run_terminal(
                api_dependencies,
                run_id=run_id,
                user_id=user_id,
                final_status=final_status,
                status_message=error_message,
                result_excerpt=latest_excerpt,
            )
        except RECOVERABLE_EXCEPTIONS as cleanup_exception:
            coerced_cleanup = coerce_to_soai_error(
                cleanup_exception,
                operation=operation,
            )
            log_exception(
                logger,
                coerced_cleanup,
                message=(
                    "Automation run cancellation persistence failed during cleanup."
                    if is_cancelled
                    else "Automation run error persistence failed during cleanup."
                ),
                operation=operation,
                level="error",
                details={"run_id": run_id, "automation_id": automation_id},
            )
        else:
            if completed_run is None:
                existing_status: str | None = None
                try:
                    existing_run = await api_dependencies.database_automation_runs.get_run(
                        run_id,
                        user_id,
                    )
                except RECOVERABLE_EXCEPTIONS as read_exception:
                    coerced_read = coerce_to_soai_error(
                        read_exception,
                        operation=operation,
                    )
                    log_handled_exception(
                        logger,
                        coerced_read,
                        message="Failed to fetch automation run after persistence failure (non-critical).",
                        operation=operation,
                        level="warning",
                        details={"run_id": run_id, "automation_id": automation_id},
                    )
                else:
                    existing_status_value = (
                        existing_run.get("status") if isinstance(existing_run, dict) else None
                    )
                    existing_status = (
                        existing_status_value.strip()
                        if isinstance(existing_status_value, str) and existing_status_value.strip()
                        else None
                    )
                if existing_status in {"completed", "error", "cancelled", "abandoned"}:
                    run_error_recorded = True
                else:
                    log_exception(
                        logger,
                        StateError("Automation run failure could not be recorded."),
                        message=(
                            "Automation run cancellation state could not be persisted."
                            if is_cancelled
                            else "Automation run error state could not be persisted."
                        ),
                        operation=operation,
                        level="error",
                        details={"run_id": run_id, "automation_id": automation_id},
                    )
            else:
                run_error_recorded = True
    try:
        await finalize_automation_run_task_terminal(
            api_dependencies,
            owner_task_id=owner_task_id,
            final_status=final_status,
            error_code=int(coerced.http_status),
            error_message=error_message,
        )
    except RECOVERABLE_EXCEPTIONS as finalize_exception:
        log_message = (
            (
                "Automation run task error finalization failed after error persistence."
                if run_error_recorded
                else "Automation run task error finalization failed during cleanup."
            )
            if is_timeout
            else (
                (
                    "Automation run task cancellation finalization failed after cancellation persistence."
                    if run_error_recorded
                    else "Automation run task cancellation finalization failed during cleanup."
                )
                if is_cancelled
                else (
                    "Automation run task error finalization failed after error persistence."
                    if run_error_recorded
                    else "Automation run task error finalization failed during cleanup."
                )
            )
        )
        coerced_finalize = coerce_to_soai_error(
            finalize_exception,
            operation=operation,
        )
        log_exception(
            logger,
            coerced_finalize,
            message=log_message,
            operation=operation,
            level="error",
            details={"run_id": run_id, "automation_id": automation_id},
        )
        return
