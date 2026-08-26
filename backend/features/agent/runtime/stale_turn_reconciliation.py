"""SoAI - Stale running turn reconciliation persistence [backend/features/agent/runtime/stale_turn_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_ABANDONED,
    AGENT_TURN_STATUS_RUNNING,
)
from core.agent.turn_record_fields import read_turn_int, read_turn_optional_text
from core.agent.turn_state_record_rewrites import (
    build_terminal_turn_state_request_from_record,
)
from core.database.requests import WriteAgentTurnStateRequest
from core.timing.epoch import epoch_ms
from features.agent.runtime.stale_turn_terminal_outcome import StaleTurnTerminalOutcome
from features.agent.runtime.stale_turn_tool_call_finalization import (
    finalize_stale_turn_active_tool_calls_noncritical,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict

__all__ = (
    "build_stale_turn_terminal_request",
    "persist_stale_turn_abandoned",
    "persist_stale_turn_terminal_outcome",
    "refresh_running_turn_if_current",
)


def build_stale_turn_terminal_request(
    *,
    record: JSONDict,
    outcome: StaleTurnTerminalOutcome,
    finished_at_ms: int,
) -> WriteAgentTurnStateRequest:
    return build_terminal_turn_state_request_from_record(
        record=record,
        execution_token=str(record.get("execution_token") or ""),
        status=outcome.status,
        iteration_index=max(0, read_turn_int(record, "iteration_index") or 0),
        sequence=max(0, read_turn_int(record, "sequence") or 0),
        turn_cancellation_id=read_turn_optional_text(record, "turn_cancellation_id"),
        active_inference_cancellation_id=None,
        reached_max_iterations=record.get("reached_max_iterations") is True,
        error_message=outcome.error_message,
        error_type=outcome.error_type,
        updated_at_ms=finished_at_ms,
        finished_at_ms=finished_at_ms,
    )


async def persist_stale_turn_terminal_outcome(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    record: JSONDict,
    tool_calls: list[JSONDict],
    outcome: StaleTurnTerminalOutcome,
    logger: LoggerProtocol,
    completed_at_ms: int | None = None,
    task_registry: TaskRegistryLifecycleView | None = None,
) -> None:
    finished_at_ms = completed_at_ms if completed_at_ms is not None else epoch_ms()
    await database_agent_turns.write_turn_state(
        build_stale_turn_terminal_request(
            record=record,
            outcome=outcome,
            finished_at_ms=finished_at_ms,
        ),
    )
    await finalize_stale_turn_active_tool_calls_noncritical(
        database_tool_calls=database_tool_calls,
        task_registry=task_registry,
        tool_calls=tool_calls,
        turn_status=outcome.status,
        turn_error_message=outcome.error_message,
        completed_at_ms=finished_at_ms,
        logger=logger,
    )


async def persist_stale_turn_abandoned(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    record: JSONDict,
) -> None:
    finished_at_ms = epoch_ms()
    await database_agent_turns.write_turn_state(
        build_stale_turn_terminal_request(
            record=record,
            outcome=StaleTurnTerminalOutcome(
                status=AGENT_TURN_STATUS_ABANDONED,
                error_message=None,
                error_type=None,
            ),
            finished_at_ms=finished_at_ms,
        ),
    )


async def refresh_running_turn_if_current(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    conv_id: str,
    user_id: int,
    turn_id: str,
) -> JSONDict | None:
    refreshed_turn = await database_agent_turns.get_turn(
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
    )
    if (
        isinstance(refreshed_turn, dict)
        and str(refreshed_turn.get("status") or "").strip() == AGENT_TURN_STATUS_RUNNING
    ):
        return refreshed_turn
    return None
