"""SoAI - Shutdown reconciliation entrypoints for app composition [backend/app/composition/shutdown_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial

from app.lifecycle.entries import LifecycleEntry
from app.lifecycle.results import LifecycleFailure
from app.lifecycle.runner import LifecycleRunner
from core.automation.protocols_database import DatabaseAutomationRunSchedulerProtocol
from core.conversations.protocols_database_agents import (
    DatabaseAgentTurnProcessBoundaryProtocol,
    DatabaseAgentTurnsProtocol,
)
from core.logging.protocols import LoggerProtocol
from core.timing.epoch import epoch_ms
from core.tool_calls.protocols import DatabaseToolCallsProtocol
from features.agent.runtime.process_boundary_turn_reconciliation import (
    ProcessBoundaryMode,
    reconcile_turns_at_process_boundary,
)

__all__ = ("reconcile_runtime_state_on_shutdown",)

_SHUTDOWN_AUTOMATION_RUN_MESSAGE = "server shutting down"


async def reconcile_runtime_state_on_shutdown(
    *,
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    database_automation_run_scheduler: DatabaseAutomationRunSchedulerProtocol,
    logger: LoggerProtocol,
    timeout_sec: float,
) -> list[LifecycleFailure]:
    entries = (
        LifecycleEntry(
            component_name="Agent Turn Shutdown Reconciliation",
            phase="shutdown_reconciliation",
            action=partial(
                _reconcile_agent_turns_on_shutdown,
                database_agent_turn_process_boundary=database_agent_turn_process_boundary,
                database_agent_turns=database_agent_turns,
                database_tool_calls=database_tool_calls,
                logger=logger,
            ),
            timeout_sec=timeout_sec,
            critical=True,
        ),
        LifecycleEntry(
            component_name="Automation Run Shutdown Reconciliation",
            phase="shutdown_reconciliation",
            action=partial(
                _reconcile_automation_runs_on_shutdown,
                database_automation_run_scheduler=database_automation_run_scheduler,
                logger=logger,
            ),
            timeout_sec=timeout_sec,
            critical=True,
        ),
    )
    return await LifecycleRunner(logger=logger).run_entries_continue(entries)


async def _reconcile_agent_turns_on_shutdown(
    *,
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
) -> None:
    reconciled = await reconcile_turns_at_process_boundary(
        database_agent_turn_process_boundary=database_agent_turn_process_boundary,
        database_agent_turns=database_agent_turns,
        database_tool_calls=database_tool_calls,
        mode=ProcessBoundaryMode.SHUTDOWN,
    )
    if reconciled:
        logger.warning("Reconciled %d running agent turn(s) at shutdown.", reconciled)


async def _reconcile_automation_runs_on_shutdown(
    *,
    database_automation_run_scheduler: DatabaseAutomationRunSchedulerProtocol,
    logger: LoggerProtocol,
) -> None:
    restarted_runs = await database_automation_run_scheduler.mark_restarted_running_runs(
        now_ms=epoch_ms(),
        status_message=_SHUTDOWN_AUTOMATION_RUN_MESSAGE,
    )
    if restarted_runs:
        logger.warning(
            "Reconciled %d running automation run(s) at shutdown.",
            len(restarted_runs),
        )
