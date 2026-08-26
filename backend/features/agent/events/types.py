"""SoAI - Agent realtime event definitions [backend/features/agent/events/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_COMPLETED,
    AGENT_TURN_STATUS_ERROR,
    AGENT_TURN_STATUS_RUNNING,
)
from core.events.types_base import Event

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "AgentItemCompletedEvent",
    "AgentItemDeltaEvent",
    "AgentItemStartedEvent",
    "AgentModeChangedEvent",
    "AgentPlanUpdatedEvent",
    "AgentTodoUpdatedEvent",
    "AgentTurnCompletedEvent",
    "AgentTurnErrorEvent",
    "AgentTurnStartedEvent",
)


@dataclass(kw_only=True, slots=True)
class AgentTurnStartedEvent(Event):
    user_id: int
    conv_id: str
    turn_id: str
    iteration_index: int
    sequence: int
    mode: str
    max_iterations: int
    item_id: str | None = None
    event_type: str = "turn/started"
    status: str = AGENT_TURN_STATUS_RUNNING


@dataclass(kw_only=True, slots=True)
class AgentTurnCompletedEvent(Event):
    user_id: int
    conv_id: str
    turn_id: str
    iteration_index: int
    sequence: int
    total_iterations: int
    reached_max_iterations: bool
    item_id: str | None = None
    event_type: str = "turn/completed"
    status: str = AGENT_TURN_STATUS_COMPLETED


@dataclass(kw_only=True, slots=True)
class AgentTurnErrorEvent(Event):
    user_id: int
    conv_id: str
    turn_id: str
    iteration_index: int
    sequence: int
    message: str
    error_type: str
    item_id: str | None = None
    event_type: str = "turn/error"
    status: str = AGENT_TURN_STATUS_ERROR


@dataclass(kw_only=True, slots=True)
class AgentItemStartedEvent(Event):
    user_id: int
    conv_id: str
    turn_id: str
    item_id: str
    iteration_index: int
    sequence: int
    item_type: str
    event_type: str = "item/started"
    status: str = AGENT_TURN_STATUS_RUNNING


@dataclass(kw_only=True, slots=True)
class AgentItemDeltaEvent(Event):
    user_id: int
    conv_id: str
    turn_id: str
    item_id: str
    iteration_index: int
    sequence: int
    text_delta: str
    event_type: str = "item/agentMessage/delta"
    status: str = AGENT_TURN_STATUS_RUNNING


@dataclass(kw_only=True, slots=True)
class AgentItemCompletedEvent(Event):
    user_id: int
    conv_id: str
    turn_id: str
    item_id: str
    iteration_index: int
    sequence: int
    final_text: str
    event_type: str = "item/completed"
    status: str = AGENT_TURN_STATUS_COMPLETED


@dataclass(kw_only=True, slots=True)
class AgentTodoUpdatedEvent(Event):
    user_id: int
    conv_id: str
    turn_id: str
    iteration_index: int
    sequence: int
    revision: int
    explanation: str | None
    todo: list[dict[str, JSONValue]]
    item_id: str | None = None
    event_type: str = "todo/updated"
    status: str = AGENT_TURN_STATUS_COMPLETED


@dataclass(kw_only=True, slots=True)
class AgentPlanUpdatedEvent(Event):
    user_id: int
    conv_id: str
    turn_id: str
    iteration_index: int
    sequence: int
    revision: int
    title: str | None
    markdown: str | None
    item_id: str | None = None
    event_type: str = "plan/updated"
    status: str = AGENT_TURN_STATUS_COMPLETED


@dataclass(kw_only=True, slots=True)
class AgentModeChangedEvent(Event):
    user_id: int
    conv_id: str
    turn_id: str
    iteration_index: int
    sequence: int
    mode: str
    item_id: str | None = None
    event_type: str = "mode/changed"
    status: str = AGENT_TURN_STATUS_COMPLETED
