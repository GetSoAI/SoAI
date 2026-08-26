"""SoAI - Agent turn-loop compaction state transition [backend/features/agent/runtime/turn_loop_compaction_transition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.types.json import JSONDict
    from features.agent.runtime.turn_loop_models import TurnLoopCompactionCallback

__all__ = (
    "TurnLoopRetryCompactionTransition",
    "advance_retry_after_compaction",
    "compact_turn_loop_history",
)


@dataclass(frozen=True, slots=True)
class TurnLoopRetryCompactionTransition:
    iteration_index: int
    message_history: list[JSONDict]
    boundary_source_messages: list[JSONDict]
    cancelled: bool


async def compact_turn_loop_history(
    *,
    compact_messages: TurnLoopCompactionCallback,
    iteration_index: int,
    message_history: list[JSONDict],
    boundary_source_messages: list[JSONDict],
) -> tuple[list[JSONDict], list[JSONDict]]:
    compaction_result = await compact_messages(
        iteration_index,
        message_history,
        boundary_source_messages,
    )
    return (
        compaction_result.prompt_messages,
        compaction_result.boundary_source_messages,
    )


async def advance_retry_after_compaction(
    *,
    compact_messages: TurnLoopCompactionCallback,
    iteration_index: int,
    message_history: list[JSONDict],
    boundary_source_messages: list[JSONDict],
    turn_cancelled: Callable[[], Awaitable[bool]],
) -> TurnLoopRetryCompactionTransition:
    if await turn_cancelled():
        return TurnLoopRetryCompactionTransition(
            iteration_index=iteration_index,
            message_history=message_history,
            boundary_source_messages=boundary_source_messages,
            cancelled=True,
        )
    next_iteration_index = iteration_index + 1
    next_message_history, next_boundary_source_messages = await compact_turn_loop_history(
        compact_messages=compact_messages,
        iteration_index=next_iteration_index,
        message_history=message_history,
        boundary_source_messages=boundary_source_messages,
    )
    return TurnLoopRetryCompactionTransition(
        iteration_index=next_iteration_index,
        message_history=next_message_history,
        boundary_source_messages=next_boundary_source_messages,
        cancelled=await turn_cancelled(),
    )
