"""SoAI - Shutdown reconciliation entrypoints for app composition [backend/app/composition/shutdown_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.automation.protocols_database import DatabaseAutomationRunSchedulerProtocol
from core.conversations.protocols_database_agents import (
    DatabaseAgentTurnProcessBoundaryProtocol,
    DatabaseAgentTurnsProtocol,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.timing.epoch import epoch_ms
from core.tool_calls.protocols import DatabaseToolCallsProtocol
from features.agent.runtime.process_boundary_turn_reconciliation import (
    ProcessBoundaryMode,
    reconcile_turns_at_process_boundary,
)

__all__ = ("reconcile_runtime_state_on_shutdown",)

OPERATION_RECONCILE_AGENT_TURNS_SHUTDOWN = "app.composition.reconcile_agent_turns_on_shutdown"
OPERATION_RECONCILE_AUTOMATION_RUNS_SHUTDOWN = (
    "app.composition.reconcile_automation_runs_on_shutdown"
)
_SHUTDOWN_AUTOMATION_RUN_MESSAGE = "server shutting down"


async def reconcile_runtime_state_on_shutdown(
    *,
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    database_automation_run_scheduler: DatabaseAutomationRunSchedulerProtocol,
    logger: LoggerProtocol,
) -> None:
    await _reconcile_agent_turns_on_shutdown(
        database_agent_turn_process_boundary=database_agent_turn_process_boundary,
        database_agent_turns=database_agent_turns,
        database_tool_calls=database_tool_calls,
        logger=logger,
    )
    await _reconcile_automation_runs_on_shutdown(
        database_automation_run_scheduler=database_automation_run_scheduler,
        logger=logger,
    )


async def _reconcile_agent_turns_on_shutdown(
    *,
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
) -> None:
    try:
        reconciled = await reconcile_turns_at_process_boundary(
            database_agent_turn_process_boundary=database_agent_turn_process_boundary,
            database_agent_turns=database_agent_turns,
            database_tool_calls=database_tool_calls,
            mode=ProcessBoundaryMode.SHUTDOWN,
        )
        if reconciled:
            logger.warning("Reconciled %d running agent turn(s) at shutdown.", reconciled)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Agent turn shutdown reconciliation failed",
            operation=OPERATION_RECONCILE_AGENT_TURNS_SHUTDOWN,
            level="warning",
        )
    except SoAIError as exception:
        log_exception(
            logger,
            exception,
            message="Agent turn shutdown reconciliation failed",
            operation=OPERATION_RECONCILE_AGENT_TURNS_SHUTDOWN,
            level="warning",
        )
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_RECONCILE_AGENT_TURNS_SHUTDOWN,
        )
        log_exception(
            logger,
            coerced,
            message="Unexpected agent turn shutdown reconciliation failure",
            operation=OPERATION_RECONCILE_AGENT_TURNS_SHUTDOWN,
            level="warning",
        )


async def _reconcile_automation_runs_on_shutdown(
    *,
    database_automation_run_scheduler: DatabaseAutomationRunSchedulerProtocol,
    logger: LoggerProtocol,
) -> None:
    try:
        restarted_runs = await database_automation_run_scheduler.mark_restarted_running_runs(
            now_ms=epoch_ms(),
            status_message=_SHUTDOWN_AUTOMATION_RUN_MESSAGE,
        )
        if restarted_runs:
            logger.warning(
                "Reconciled %d running automation run(s) at shutdown.",
                len(restarted_runs),
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Automation run shutdown reconciliation failed",
            operation=OPERATION_RECONCILE_AUTOMATION_RUNS_SHUTDOWN,
            level="warning",
        )
    except SoAIError as exception:
        log_exception(
            logger,
            exception,
            message="Automation run shutdown reconciliation failed",
            operation=OPERATION_RECONCILE_AUTOMATION_RUNS_SHUTDOWN,
            level="warning",
        )
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_RECONCILE_AUTOMATION_RUNS_SHUTDOWN,
        )
        log_exception(
            logger,
            coerced,
            message="Unexpected automation run shutdown reconciliation failure",
            operation=OPERATION_RECONCILE_AUTOMATION_RUNS_SHUTDOWN,
            level="warning",
        )
