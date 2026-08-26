"""SoAI - Shared realtime agent event type groupings [backend/features/api/routes/system/events/agent_event_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, TypeGuard

from core.events.types_base import Event
from core.events.types_system import (
    ToolCallCompletedEvent,
    ToolCallCreatedEvent,
    ToolCallStartedEvent,
)
from features.agent.events.subagent_types import (
    SubagentAbandonedEvent,
    SubagentCancelledEvent,
    SubagentCompletedEvent,
    SubagentErrorEvent,
    SubagentMaxIterationsEvent,
    SubagentRunningEvent,
    SubagentSpawnedEvent,
)
from features.agent.events.types import (
    AgentItemCompletedEvent,
    AgentItemDeltaEvent,
    AgentItemStartedEvent,
    AgentModeChangedEvent,
    AgentPlanUpdatedEvent,
    AgentTodoUpdatedEvent,
    AgentTurnCompletedEvent,
    AgentTurnErrorEvent,
    AgentTurnStartedEvent,
)

__all__ = (
    "REALTIME_AGENT_ACTION_EVENT_TYPES",
    "REALTIME_AGENT_DELTA_EVENT_TYPES",
    "REALTIME_AGENT_EVENT_TYPES",
    "is_user_scoped_agent_event",
)

REALTIME_AGENT_ACTION_EVENT_TYPES: tuple[type[Event], ...] = (
    AgentTurnStartedEvent,
    AgentTurnCompletedEvent,
    AgentTurnErrorEvent,
    AgentItemStartedEvent,
    AgentItemCompletedEvent,
    ToolCallCreatedEvent,
    ToolCallStartedEvent,
    ToolCallCompletedEvent,
    AgentTodoUpdatedEvent,
    AgentPlanUpdatedEvent,
    AgentModeChangedEvent,
    SubagentSpawnedEvent,
    SubagentRunningEvent,
    SubagentCompletedEvent,
    SubagentMaxIterationsEvent,
    SubagentErrorEvent,
    SubagentAbandonedEvent,
    SubagentCancelledEvent,
)

REALTIME_AGENT_DELTA_EVENT_TYPES: tuple[type[Event], ...] = (AgentItemDeltaEvent,)

REALTIME_AGENT_EVENT_TYPES: tuple[type[Event], ...] = (
    REALTIME_AGENT_ACTION_EVENT_TYPES + REALTIME_AGENT_DELTA_EVENT_TYPES
)

if TYPE_CHECKING:
    type UserScopedAgentEvent = (
        AgentTurnStartedEvent
        | AgentTurnCompletedEvent
        | AgentTurnErrorEvent
        | AgentItemStartedEvent
        | AgentItemDeltaEvent
        | AgentItemCompletedEvent
        | ToolCallCreatedEvent
        | ToolCallStartedEvent
        | ToolCallCompletedEvent
        | AgentTodoUpdatedEvent
        | AgentPlanUpdatedEvent
        | AgentModeChangedEvent
        | SubagentSpawnedEvent
        | SubagentRunningEvent
        | SubagentCompletedEvent
        | SubagentMaxIterationsEvent
        | SubagentErrorEvent
        | SubagentAbandonedEvent
        | SubagentCancelledEvent
    )


def is_user_scoped_agent_event(event: Event) -> TypeGuard[UserScopedAgentEvent]:
    return isinstance(event, REALTIME_AGENT_EVENT_TYPES)
