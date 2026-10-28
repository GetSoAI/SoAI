"""SoAI - Agent turn process-boundary reconciliation [backend/features/agent/runtime/process_boundary_turn_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_ABANDONED
from core.agent.turn_record_fields import read_turn_int
from core.agent.turn_write_conflicts import (
    AgentTurnFinalizedWriteConflictError,
    AgentTurnStaleProgressError,
)
from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError, SoAIError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.boot_id import get_boot_id
from core.timing.epoch import epoch_ms
from features.agent.runtime.process_boundary_tool_call_reconciliation import (
    repair_active_tool_calls_for_terminal_turns,
)
from features.agent.runtime.stale_turn_reconciliation import (
    build_stale_turn_terminal_request,
)
from features.agent.runtime.stale_turn_terminal_outcome import (
    resolve_stale_turn_terminal_outcome,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import (
        DatabaseAgentTurnProcessBoundaryProtocol,
        DatabaseAgentTurnsProtocol,
    )
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict

__all__ = (
    "ProcessBoundaryMode",
    "reconcile_turns_at_process_boundary",
)

_LOGGER_NAME = "SoAI.features.agent.runtime.process_boundary_turn_reconciliation"
_OPERATION = "features.agent.runtime.reconcile_turns_at_process_boundary"
_DEFAULT_RECONCILIATION_LIMIT = 20000


class ProcessBoundaryMode(str, Enum):
    STARTUP = "startup"
    SHUTDOWN = "shutdown"


async def reconcile_turns_at_process_boundary(
    *,
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    mode: ProcessBoundaryMode,
    limit: int = _DEFAULT_RECONCILIATION_LIMIT,
) -> int:
    if limit < 1:
        return 0
    failures: list[SoAIError] = []
    if mode is ProcessBoundaryMode.STARTUP:
        stale_records = (
            await database_agent_turn_process_boundary.query_running_turns_from_other_boots(
                current_boot_id=get_boot_id(),
                limit=limit,
            )
        )
    else:
        try:
            stale_records = await database_agent_turn_process_boundary.query_all_running_turns(
                limit=limit,
            )
        except TaskCancelledError:
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            stale_records = []
            failures.append(
                ProcessError(
                    "Failed to query running agent turns during shutdown reconciliation.",
                    operation=_OPERATION,
                    cause=exception,
                    details={"group": "Running Agent Turns"},
                )
            )
    logger = get_logger(_LOGGER_NAME)
    reconciled_count = 0
    for record in stale_records:
        try:
            finalized_record = await _finalize_stale_running_turn_if_current(
                database_agent_turns=database_agent_turns,
                database_tool_calls=database_tool_calls,
                record=record,
                shutdown_requested=mode is ProcessBoundaryMode.SHUTDOWN,
            )
        except (AgentTurnFinalizedWriteConflictError, AgentTurnStaleProgressError):
            continue
        except TaskCancelledError:
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            failure = ProcessError(
                "Failed to reconcile stale agent turn at process boundary.",
                operation=_OPERATION,
                cause=exception,
                details={
                    "conv_id": str(record.get("conv_id") or ""),
                    "turn_id": str(record.get("turn_id") or ""),
                    "turn_scope": str(record.get("turn_scope") or ""),
                },
            )
            if mode is ProcessBoundaryMode.SHUTDOWN:
                failures.append(failure)
            else:
                log_exception(
                    logger,
                    exception,
                    message=failure.message,
                    operation=_OPERATION,
                    details=failure.details,
                    level="warning",
                )
            continue
        if finalized_record is None:
            continue
        reconciled_count += 1
    await repair_active_tool_calls_for_terminal_turns(
        database_agent_turn_process_boundary=database_agent_turn_process_boundary,
        database_tool_calls=database_tool_calls,
        logger=logger,
        failures=failures if mode is ProcessBoundaryMode.SHUTDOWN else None,
        limit=limit,
    )
    if mode is ProcessBoundaryMode.SHUTDOWN:
        failures.extend(await _verify_shutdown_work_settled(database_agent_turn_process_boundary))
    if failures and mode is ProcessBoundaryMode.SHUTDOWN:
        raise ProcessError(
            "Shutdown process-boundary reconciliation left durable work unsettled.",
            operation=_OPERATION,
            cause=failures[0],
            details={
                "failures": [
                    {
                        "message": failure.message,
                        "details": failure.details,
                        "cause": str(failure.cause),
                    }
                    for failure in failures
                ],
                "reconciled_count": reconciled_count,
            },
        )
    return reconciled_count


async def _verify_shutdown_work_settled(
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
) -> list[SoAIError]:
    failures: list[SoAIError] = []
    for group_name, query in (
        ("Running Agent Turns", database_agent_turn_process_boundary.query_all_running_turns),
        (
            "Subagent Parent Tool Calls",
            database_agent_turn_process_boundary.query_terminal_subagent_turns_with_active_parent_tool_calls,
        ),
        (
            "Root Turn Tool Calls",
            database_agent_turn_process_boundary.query_terminal_root_turn_active_tool_calls,
        ),
    ):
        try:
            remaining = await query(limit=1)
        except TaskCancelledError:
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            failures.append(
                ProcessError(
                    f"Could not verify settled shutdown work for {group_name}.",
                    operation=_OPERATION,
                    cause=exception,
                    details={"group": group_name},
                )
            )
            continue
        if remaining:
            record = remaining[0]
            failures.append(
                ProcessError(
                    f"Unsettled durable work remains after bounded shutdown reconciliation for {group_name}.",
                    operation=_OPERATION,
                    details={
                        "group": group_name,
                        "conv_id": str(record.get("conv_id") or ""),
                        "turn_id": str(record.get("turn_id") or ""),
                        "parent_tool_call_id": str(record.get("parent_tool_call_id") or ""),
                        "tool_storage_call_id": str(record.get("tool_storage_call_id") or ""),
                    },
                )
            )
    return failures


async def _finalize_stale_running_turn_if_current(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    record: JSONDict,
    shutdown_requested: bool,
) -> JSONDict | None:
    conv_id = str(record.get("conv_id") or "")
    user_id = max(0, read_turn_int(record, "user_id") or 0)
    turn_id = str(record.get("turn_id") or "")
    execution_token = str(record.get("execution_token") or "")
    tool_calls = await database_tool_calls.get_tool_calls_for_turn(conv_id, turn_id)
    outcome = resolve_stale_turn_terminal_outcome(
        record=record,
        tool_calls=tool_calls,
        shutdown_requested=shutdown_requested,
    )
    finished_at_ms = epoch_ms()
    if outcome.status == AGENT_TURN_STATUS_ABANDONED:
        return await database_agent_turns.abandon_running_turn_if_current(
            conv_id=conv_id,
            user_id=user_id,
            turn_id=turn_id,
            execution_token=execution_token,
            finished_at_ms=finished_at_ms,
        )
    return await database_agent_turns.write_turn_state(
        build_stale_turn_terminal_request(
            record=record,
            outcome=outcome,
            finished_at_ms=finished_at_ms,
        ),
    )
