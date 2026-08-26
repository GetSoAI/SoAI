"""SoAI - Agent running turn reconciliation [backend/features/agent/runtime/turn_state_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_ABANDONED
from core.agent.turn_record_fields import read_turn_id
from core.agent.turn_scope_values import TURN_SCOPE_ROOT
from core.database.requests import ClaimAgentTurnAbandonRequest
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from features.agent.runtime.stale_turn_reconciliation import (
    persist_stale_turn_terminal_outcome,
    refresh_running_turn_if_current,
)
from features.agent.runtime.stale_turn_terminal_outcome import (
    resolve_stale_turn_terminal_outcome,
)
from features.agent.runtime.turn_liveness import (
    partition_running_root_turns_by_liveness,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
    from core.tasks.protocols import TokenCollectionProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict

__all__ = (
    "collect_stale_running_turn_claims",
    "reconcile_running_turns",
)

LOGGER_NAME = "SoAI.features.agent.turn_state_reconciliation"


async def reconcile_running_turns(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    conv_id: str,
    user_id: int,
    exclude_turn_id: str | None = None,
) -> list[JSONDict]:
    logger = get_logger(LOGGER_NAME)
    live_turns, stale_turns = await partition_running_root_turns_by_liveness(
        database_agent_turns=database_agent_turns,
        task_registry_queries=task_registry_queries,
        token_collection=token_collection,
        conv_id=conv_id,
        user_id=user_id,
        exclude_turn_id=exclude_turn_id,
    )
    for stale_turn in stale_turns:
        tool_calls = await database_tool_calls.get_tool_calls_for_turn(
            conv_id=conv_id,
            turn_id=str(stale_turn.get("turn_id") or ""),
        )
        outcome = resolve_stale_turn_terminal_outcome(record=stale_turn, tool_calls=tool_calls)
        try:
            await persist_stale_turn_terminal_outcome(
                database_agent_turns=database_agent_turns,
                database_tool_calls=database_tool_calls,
                record=stale_turn,
                tool_calls=tool_calls,
                outcome=outcome,
                logger=logger,
            )
        except ValidationError:
            refreshed_turn = await refresh_running_turn_if_current(
                database_agent_turns=database_agent_turns,
                conv_id=conv_id,
                user_id=user_id,
                turn_id=str(stale_turn.get("turn_id") or ""),
            )
            if refreshed_turn is not None:
                live_turns.append(refreshed_turn)
    return live_turns


async def collect_stale_running_turn_claims(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    conv_id: str,
    user_id: int,
    turn_scope: str = TURN_SCOPE_ROOT,
    exclude_turn_id: str | None = None,
) -> tuple[ClaimAgentTurnAbandonRequest, ...]:
    if turn_scope != TURN_SCOPE_ROOT:
        return ()
    logger = get_logger(LOGGER_NAME)
    _live_turns, stale_turns = await partition_running_root_turns_by_liveness(
        database_agent_turns=database_agent_turns,
        task_registry_queries=task_registry_queries,
        token_collection=token_collection,
        conv_id=conv_id,
        user_id=user_id,
        exclude_turn_id=exclude_turn_id,
    )
    stale_claims: list[ClaimAgentTurnAbandonRequest] = []
    for stale_turn in stale_turns:
        tool_calls = await database_tool_calls.get_tool_calls_for_turn(
            conv_id=conv_id,
            turn_id=str(stale_turn.get("turn_id") or ""),
        )
        outcome = resolve_stale_turn_terminal_outcome(record=stale_turn, tool_calls=tool_calls)
        if outcome.status != AGENT_TURN_STATUS_ABANDONED:
            try:
                await persist_stale_turn_terminal_outcome(
                    database_agent_turns=database_agent_turns,
                    database_tool_calls=database_tool_calls,
                    record=stale_turn,
                    tool_calls=tool_calls,
                    outcome=outcome,
                    logger=logger,
                )
            except ValidationError:
                continue
            continue
        stale_turn_id = read_turn_id(stale_turn)
        execution_token = str(stale_turn.get("execution_token") or "").strip()
        if stale_turn_id is None or not execution_token:
            continue
        stale_claims.append(
            ClaimAgentTurnAbandonRequest(turn_id=stale_turn_id, execution_token=execution_token),
        )
    return tuple(stale_claims)
