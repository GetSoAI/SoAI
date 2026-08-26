"""SoAI - Subagent realtime event definitions [backend/features/agent/events/subagent_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.status_values import (
    SUBAGENT_STATUS_ABANDONED,
    SUBAGENT_STATUS_ACCEPTED,
    SUBAGENT_STATUS_CANCELLED,
    SUBAGENT_STATUS_COMPLETED,
    SUBAGENT_STATUS_ERROR,
    SUBAGENT_STATUS_MAX_ITERATIONS,
    SUBAGENT_STATUS_RUNNING,
)
from core.events.types_base import Event

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "SubagentAbandonedEvent",
    "SubagentCancelledEvent",
    "SubagentCompletedEvent",
    "SubagentErrorEvent",
    "SubagentMaxIterationsEvent",
    "SubagentRunningEvent",
    "SubagentSpawnedEvent",
)


@dataclass(kw_only=True, slots=True)
class SubagentEventBase(Event):
    user_id: int
    conv_id: str
    parent_turn_id: str
    parent_tool_call_id: str
    parent_iteration_index: int
    subagent_id: str
    execution_type: str
    display_name: str | None
    mode: str
    owner_task_id: str | None
    status_message: str | None
    started_at_ms: int
    updated_at_ms: int
    finished_at_ms: int | None
    requested_model: str | None
    result_text: str | None
    result_text_delta: str | None = None
    error_message: str | None
    error_type: str | None
    token_usage: JSONDict | None
    item_id: str | None = None


@dataclass(kw_only=True, slots=True)
class SubagentSpawnedEvent(SubagentEventBase):
    event_type: str = "subagent/spawned"
    status: str = SUBAGENT_STATUS_ACCEPTED


@dataclass(kw_only=True, slots=True)
class SubagentRunningEvent(SubagentEventBase):
    event_type: str = "subagent/running"
    status: str = SUBAGENT_STATUS_RUNNING


@dataclass(kw_only=True, slots=True)
class SubagentCompletedEvent(SubagentEventBase):
    event_type: str = "subagent/completed"
    status: str = SUBAGENT_STATUS_COMPLETED


@dataclass(kw_only=True, slots=True)
class SubagentMaxIterationsEvent(SubagentEventBase):
    event_type: str = "subagent/max_iterations"
    status: str = SUBAGENT_STATUS_MAX_ITERATIONS


@dataclass(kw_only=True, slots=True)
class SubagentErrorEvent(SubagentEventBase):
    event_type: str = "subagent/error"
    status: str = SUBAGENT_STATUS_ERROR


@dataclass(kw_only=True, slots=True)
class SubagentAbandonedEvent(SubagentEventBase):
    event_type: str = "subagent/abandoned"
    status: str = SUBAGENT_STATUS_ABANDONED


@dataclass(kw_only=True, slots=True)
class SubagentCancelledEvent(SubagentEventBase):
    event_type: str = "subagent/cancelled"
    status: str = SUBAGENT_STATUS_CANCELLED
