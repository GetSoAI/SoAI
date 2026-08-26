"""SoAI - Automation run reconciliation helpers [backend/app/background/automation_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.automation.automation_constants import AUTOMATION_TIMEOUT_REASON_PREFIX
from core.automation.automation_identifiers import build_automation_run_cancellation_id
from core.automation.automation_run_task_lifecycle import (
    read_automation_run_owner_task_id,
)
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int
from core.validation.record_fields import require_int, require_non_empty_str
from features.automation.run_terminal_transitions import (
    complete_automation_run_terminal,
    finalize_automation_run_task_terminal,
)

if TYPE_CHECKING:
    from app.background.internal_protocols import (
        AutomationRunReconciliationDependenciesProtocol,
    )
    from core.automation.protocols_database import (
        DatabaseAutomationRunSchedulerProtocol,
    )
    from features.automation.run_terminal_transitions import AutomationRunTerminalStatus

__all__ = (
    "reconcile_automation_runs",
    "reconcile_queued_automation_runs",
    "reconcile_stale_running_automation_runs",
)

_STALE_RUNNING_GRACE_MS: int = 5_000
_STALE_RUNNING_RECONCILIATION_LIMIT: int = 500
_LOGGER_NAME = "SoAI.app.background.automation_reconciliation"
_OPERATION_RECONCILE_STALE_RUNNING = (
    "app.background.automation_reconciliation.reconcile_stale_running"
)


async def reconcile_automation_runs(
    api_dependencies: AutomationRunReconciliationDependenciesProtocol,
    database_automation_run_scheduler: DatabaseAutomationRunSchedulerProtocol,
    *,
    enqueue_run_id: Callable[[str], None],
) -> None:
    restarted_runs = await database_automation_run_scheduler.mark_restarted_running_runs(
        now_ms=epoch_ms(),
        status_message="backend restarted",
    )
    for restarted_run in restarted_runs:
        await finalize_automation_run_task_terminal(
            api_dependencies,
            owner_task_id=read_automation_run_owner_task_id(restarted_run),
            final_status="error",
            error_message="backend restarted",
        )
    await reconcile_queued_automation_runs(
        database_automation_run_scheduler,
        enqueue_run_id=enqueue_run_id,
    )


async def reconcile_stale_running_automation_runs(
    api_dependencies: AutomationRunReconciliationDependenciesProtocol,
    database_automation_run_scheduler: DatabaseAutomationRunSchedulerProtocol,
    *,
    now_ms: int,
    limit: int = _STALE_RUNNING_RECONCILIATION_LIMIT,
) -> int:
    logger = get_logger(_LOGGER_NAME)
    if not is_strict_int(now_ms) or now_ms <= 0:
        raise StateError("Automation stale reconciliation requires a valid now_ms.")
    if not is_strict_int(limit) or limit < 1:
        raise StateError("Automation stale reconciliation requires a positive limit.")
    running_runs = await database_automation_run_scheduler.list_running_run_summaries(
        limit=limit,
    )
    reconciled = 0
    for run_record in running_runs:
        try:
            run_id = require_non_empty_str(
                run_record.get("run_id"),
                label="Automation run field 'run_id'",
                build_error=StateError,
            )
            user_id = require_int(
                run_record.get("user_id"),
                label="Automation run field 'user_id'",
                build_error=StateError,
                minimum=1,
            )
            scheduled_at_ms_value = run_record.get("scheduled_at_ms")
            if (
                not isinstance(scheduled_at_ms_value, int)
                or isinstance(scheduled_at_ms_value, bool)
                or scheduled_at_ms_value <= 0
            ):
                raise StateError("Automation run field 'scheduled_at_ms' is invalid.")
            started_at_actual_ms_value = run_record.get("started_at_actual_ms")
            started_at_ms_value = (
                started_at_actual_ms_value
                if (
                    isinstance(started_at_actual_ms_value, int)
                    and not isinstance(started_at_actual_ms_value, bool)
                    and started_at_actual_ms_value > 0
                )
                else scheduled_at_ms_value
            )
            if started_at_ms_value > now_ms:
                continue
            owner_task_id = read_automation_run_owner_task_id(run_record)
            cancellation_id = build_automation_run_cancellation_id(run_id)
            cancel_reason_value = await api_dependencies.cancellation_history.get_reason(
                cancellation_id,
            )
            cancel_reason = (
                cancel_reason_value.strip()
                if isinstance(cancel_reason_value, str) and cancel_reason_value.strip()
                else None
            )
            tokens = await api_dependencies.token_collection.get_tokens_for_scope(cancellation_id)
            has_live_worker_token = any(
                token for token in tokens if not token.thread_event.is_set()
            )
            if has_live_worker_token:
                continue
            if cancel_reason is None and (now_ms - started_at_ms_value) <= _STALE_RUNNING_GRACE_MS:
                continue
            final_status: AutomationRunTerminalStatus
            if cancel_reason is not None:
                status_message = cancel_reason[:500]
                final_status = (
                    "error"
                    if status_message.lower().startswith(AUTOMATION_TIMEOUT_REASON_PREFIX)
                    else "cancelled"
                )
            else:
                status_message = "stale (no live worker)"
                final_status = "abandoned"
            completed = await complete_automation_run_terminal(
                api_dependencies,
                run_id=run_id,
                user_id=user_id,
                final_status=final_status,
                finished_at_ms=now_ms,
                status_message=status_message,
            )
            if completed is None:
                continue
            await finalize_automation_run_task_terminal(
                api_dependencies,
                owner_task_id=owner_task_id,
                final_status=final_status,
                error_message=status_message,
            )
            reconciled += 1
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to reconcile stale running automation run (non-critical).",
                operation=_OPERATION_RECONCILE_STALE_RUNNING,
                level="warning",
            )
    return reconciled


async def reconcile_queued_automation_runs(
    database_automation_run_scheduler: DatabaseAutomationRunSchedulerProtocol,
    *,
    enqueue_run_id: Callable[[str], None],
) -> None:
    queued_run_ids = await database_automation_run_scheduler.list_queued_run_ids()
    for run_id in queued_run_ids:
        enqueue_run_id(run_id)
