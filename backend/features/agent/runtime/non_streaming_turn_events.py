"""SoAI - Agent non-streaming turn event emission helpers [backend/features/agent/runtime/non_streaming_turn_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.agent.status_values import (
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_COMPLETED,
    AGENT_TURN_STATUS_ERROR,
    AGENT_TURN_STATUS_MAX_ITERATIONS,
)
from core.events.types_base import Event
from core.runtime.soai_identifiers import create_prefixed_hex_id
from features.agent.events.types import AgentTurnCompletedEvent, AgentTurnErrorEvent
from features.agent.runtime.item_event_factories import (
    build_agent_assistant_item_completed_event,
    build_agent_assistant_item_started_event,
)

__all__ = (
    "publish_assistant_item_events",
    "publish_turn_terminal_event",
)


async def publish_assistant_item_events(
    *,
    emit_event: Callable[[Event], Awaitable[None]],
    user_id: int,
    conv_id: str,
    turn_id: str,
    iteration_index: int,
    next_action_sequence: Callable[[], Awaitable[int]],
    assistant_text: str,
) -> None:
    item_id = create_prefixed_hex_id("item", length=12)
    await emit_event(
        build_agent_assistant_item_started_event(
            user_id,
            conv_id,
            turn_id,
            item_id,
            iteration_index,
            await next_action_sequence(),
        ),
    )
    await emit_event(
        build_agent_assistant_item_completed_event(
            user_id=user_id,
            conv_id=conv_id,
            turn_id=turn_id,
            item_id=item_id,
            iteration_index=iteration_index,
            sequence=await next_action_sequence(),
            final_text=assistant_text,
        ),
    )


async def publish_turn_terminal_event(
    *,
    emit_event: Callable[[Event], Awaitable[None]],
    final_status: str,
    user_id: int,
    conv_id: str,
    turn_id: str,
    iteration_index: int,
    next_action_sequence: Callable[[], Awaitable[int]],
    reached_max_iterations: bool,
    error_message: str | None,
    error_type: str | None,
) -> None:
    if final_status in (AGENT_TURN_STATUS_COMPLETED, AGENT_TURN_STATUS_MAX_ITERATIONS):
        await emit_event(
            AgentTurnCompletedEvent(
                user_id=user_id,
                conv_id=conv_id,
                turn_id=turn_id,
                iteration_index=iteration_index,
                sequence=await next_action_sequence(),
                total_iterations=iteration_index + 1,
                reached_max_iterations=reached_max_iterations,
            ),
        )
        return
    if final_status in (AGENT_TURN_STATUS_CANCELLED, AGENT_TURN_STATUS_ERROR):
        await emit_event(
            AgentTurnErrorEvent(
                user_id=user_id,
                conv_id=conv_id,
                turn_id=turn_id,
                iteration_index=iteration_index,
                sequence=await next_action_sequence(),
                message=error_message or "Agent turn failed.",
                error_type=error_type or "server_error",
            ),
        )
