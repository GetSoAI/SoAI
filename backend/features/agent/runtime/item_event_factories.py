"""SoAI - Agent item event factories [backend/features/agent/runtime/item_event_factories.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.agent.events.types import AgentItemCompletedEvent, AgentItemStartedEvent

__all__ = (
    "build_agent_assistant_item_completed_event",
    "build_agent_assistant_item_started_event",
)


def build_agent_assistant_item_started_event(
    user_id: int,
    conv_id: str,
    turn_id: str,
    item_id: str,
    iteration_index: int,
    sequence: int,
) -> AgentItemStartedEvent:
    return AgentItemStartedEvent(
        user_id=user_id,
        conv_id=conv_id,
        turn_id=turn_id,
        item_id=item_id,
        iteration_index=iteration_index,
        sequence=sequence,
        item_type="assistant_message",
    )


def build_agent_assistant_item_completed_event(
    *,
    user_id: int,
    conv_id: str,
    turn_id: str,
    item_id: str,
    iteration_index: int,
    sequence: int,
    final_text: str,
) -> AgentItemCompletedEvent:
    return AgentItemCompletedEvent(
        user_id=user_id,
        conv_id=conv_id,
        turn_id=turn_id,
        item_id=item_id,
        iteration_index=iteration_index,
        sequence=sequence,
        final_text=final_text,
    )
