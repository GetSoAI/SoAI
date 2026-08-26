"""SoAI - Persisted terminal agent turn replay [backend/features/agent/runtime/persisted_terminal_turn_replay.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.agent.status_values import AGENT_TURN_TERMINAL_STATUSES
from core.agent.turn_snapshot import build_agent_turn_snapshot
from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol

__all__ = (
    "PersistedTerminalTurnReplay",
    "resolve_persisted_terminal_turn_replay",
)


@dataclass(frozen=True, slots=True)
class PersistedTerminalTurnReplay:
    status: str
    iteration_index: int
    assistant_text: str | None
    reached_max_iterations: bool
    error_message: str | None
    error_type: str | None


async def resolve_persisted_terminal_turn_replay(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    conv_id: str,
    user_id: int,
    turn_id: str,
) -> PersistedTerminalTurnReplay | None:
    turn_record = await database_agent_turns.get_turn(
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
    )
    turn_snapshot = build_agent_turn_snapshot(turn_record)
    if turn_snapshot is None:
        return None
    if turn_snapshot.status not in AGENT_TURN_TERMINAL_STATUSES:
        return None
    return PersistedTerminalTurnReplay(
        status=turn_snapshot.status,
        iteration_index=turn_snapshot.iteration_index,
        assistant_text=turn_snapshot.assistant_text,
        reached_max_iterations=turn_snapshot.reached_max_iterations,
        error_message=turn_snapshot.error_message,
        error_type=turn_snapshot.error_type,
    )
