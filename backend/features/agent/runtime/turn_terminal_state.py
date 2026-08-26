"""SoAI - Agent turn terminal state helpers [backend/features/agent/runtime/turn_terminal_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_COMPLETED,
    AGENT_TURN_STATUS_MAX_ITERATIONS,
)
from features.agent.runtime.tool_execution_steer_interrupt import STEER_INTERRUPTED_ERROR_TYPE
from features.agent.runtime.turn_iteration_policy_messages import get_cancelled_status

if TYPE_CHECKING:
    from core.agent.turn_state_writer import TurnStateWriter
    from features.agent.runtime.persisted_terminal_turn_replay import (
        PersistedTerminalTurnReplay,
    )

__all__ = (
    "TurnTerminalOutcome",
    "TurnTerminalSnapshot",
    "build_cancelled_turn_terminal_outcome",
    "build_completed_turn_terminal_outcome",
    "build_interrupted_turn_terminal_outcome",
    "build_max_iterations_turn_terminal_outcome",
    "resolve_turn_terminal_snapshot",
)


@dataclass(frozen=True, slots=True)
class TurnTerminalOutcome:
    status: str
    error_message: str | None
    error_type: str | None
    reached_max_iterations: bool = False
    preserve_active_subagents: bool = False


@dataclass(frozen=True, slots=True)
class TurnTerminalSnapshot:
    iteration_index: int
    assistant_text: str | None
    reached_max_iterations: bool


def build_completed_turn_terminal_outcome() -> TurnTerminalOutcome:
    return TurnTerminalOutcome(
        status=AGENT_TURN_STATUS_COMPLETED,
        error_message=None,
        error_type=None,
    )


def build_cancelled_turn_terminal_outcome() -> TurnTerminalOutcome:
    status, error_message, error_type = get_cancelled_status()
    return TurnTerminalOutcome(
        status=status,
        error_message=error_message,
        error_type=error_type,
    )


def build_interrupted_turn_terminal_outcome(error_message: str) -> TurnTerminalOutcome:
    return TurnTerminalOutcome(
        status=AGENT_TURN_STATUS_CANCELLED,
        error_message=error_message,
        error_type=STEER_INTERRUPTED_ERROR_TYPE,
        preserve_active_subagents=True,
    )


def build_max_iterations_turn_terminal_outcome() -> TurnTerminalOutcome:
    return TurnTerminalOutcome(
        status=AGENT_TURN_STATUS_MAX_ITERATIONS,
        error_message=None,
        error_type=None,
        reached_max_iterations=True,
    )


def resolve_turn_terminal_snapshot(
    *,
    loop_terminal_snapshot: TurnTerminalSnapshot | None,
    turn_state_writer: TurnStateWriter,
    persisted_terminal_turn_replay: PersistedTerminalTurnReplay | None,
) -> TurnTerminalSnapshot:
    if persisted_terminal_turn_replay is not None:
        return TurnTerminalSnapshot(
            iteration_index=persisted_terminal_turn_replay.iteration_index,
            assistant_text=persisted_terminal_turn_replay.assistant_text,
            reached_max_iterations=persisted_terminal_turn_replay.reached_max_iterations,
        )
    if loop_terminal_snapshot is not None:
        return loop_terminal_snapshot
    return TurnTerminalSnapshot(
        iteration_index=int(turn_state_writer.latest_iteration_index),
        assistant_text=turn_state_writer.latest_assistant_text,
        reached_max_iterations=bool(turn_state_writer.latest_reached_max_iterations),
    )
