"""SoAI - Subagent event factory helpers [backend/features/agent/subagents/event_payload_factories.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from core.agent.status_values import (
    SUBAGENT_STATUS_ABANDONED,
    SUBAGENT_STATUS_ACCEPTED,
    SUBAGENT_STATUS_CANCELLED,
    SUBAGENT_STATUS_COMPLETED,
    SUBAGENT_STATUS_ERROR,
    SUBAGENT_STATUS_MAX_ITERATIONS,
)
from core.errors.exceptions import ValidationError
from features.agent.events.subagent_types import (
    SubagentAbandonedEvent,
    SubagentCancelledEvent,
    SubagentCompletedEvent,
    SubagentErrorEvent,
    SubagentMaxIterationsEvent,
    SubagentRunningEvent,
    SubagentSpawnedEvent,
)
from features.agent.subagents.internal_protocols import SubagentEventPayloadProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_subagent_running_event",
    "build_subagent_spawned_event",
    "build_subagent_terminal_event",
)


class SubagentEventFields(TypedDict):
    trace_id: str | None
    event_id: str
    timestamp: float
    user_id: int
    conv_id: str
    subagent_id: str
    mode: str
    execution_type: str
    display_name: str | None
    parent_turn_id: str
    parent_tool_call_id: str
    parent_iteration_index: int
    owner_task_id: str | None
    status: str
    status_message: str | None
    requested_model: str | None
    result_text: str | None
    result_text_delta: str | None
    error_message: str | None
    error_type: str | None
    token_usage: JSONDict | None
    item_id: str | None
    started_at_ms: int
    updated_at_ms: int
    finished_at_ms: int | None


def _build_subagent_event_fields(
    *,
    payload: SubagentEventPayloadProtocol,
    status: str,
    status_message: str | None,
    result_text: str | None,
    result_text_delta: str | None,
) -> SubagentEventFields:
    return {
        "trace_id": payload.trace_id,
        "event_id": payload.event_id,
        "timestamp": payload.timestamp,
        "user_id": payload.user_id,
        "conv_id": payload.conv_id,
        "status": status,
        "parent_turn_id": payload.parent_turn_id,
        "parent_tool_call_id": payload.parent_tool_call_id,
        "parent_iteration_index": payload.parent_iteration_index,
        "subagent_id": payload.subagent_id,
        "execution_type": payload.execution_type,
        "display_name": payload.display_name,
        "mode": payload.mode,
        "owner_task_id": payload.owner_task_id,
        "status_message": status_message,
        "started_at_ms": payload.started_at_ms,
        "updated_at_ms": payload.updated_at_ms,
        "finished_at_ms": payload.finished_at_ms,
        "requested_model": payload.requested_model,
        "result_text": result_text,
        "result_text_delta": result_text_delta,
        "error_message": payload.error_message,
        "error_type": payload.error_type,
        "token_usage": payload.token_usage,
        "item_id": payload.item_id,
    }


def build_subagent_running_event(
    *,
    payload: SubagentEventPayloadProtocol,
    result_text: str | None,
    result_text_delta: str | None,
) -> SubagentRunningEvent:
    return SubagentRunningEvent(
        **_build_subagent_event_fields(
            payload=payload,
            status=payload.status,
            status_message=payload.status_message,
            result_text=result_text,
            result_text_delta=result_text_delta,
        ),
    )


def build_subagent_terminal_event(
    *,
    status: str,
    payload: SubagentEventPayloadProtocol,
) -> (
    SubagentAbandonedEvent
    | SubagentCancelledEvent
    | SubagentCompletedEvent
    | SubagentErrorEvent
    | SubagentMaxIterationsEvent
):
    event_fields = _build_subagent_event_fields(
        payload=payload,
        status=status,
        status_message=payload.status_message,
        result_text=payload.result_text,
        result_text_delta=payload.result_text_delta,
    )
    if status == SUBAGENT_STATUS_ABANDONED:
        return SubagentAbandonedEvent(**event_fields)
    if status == SUBAGENT_STATUS_CANCELLED:
        return SubagentCancelledEvent(**event_fields)
    if status == SUBAGENT_STATUS_COMPLETED:
        return SubagentCompletedEvent(**event_fields)
    if status == SUBAGENT_STATUS_ERROR:
        return SubagentErrorEvent(**event_fields)
    if status == SUBAGENT_STATUS_MAX_ITERATIONS:
        return SubagentMaxIterationsEvent(**event_fields)
    raise ValidationError(f"Subagent terminal status unsupported for event publication: {status}")


def build_subagent_spawned_event(
    *,
    payload: SubagentEventPayloadProtocol,
) -> SubagentSpawnedEvent:
    return SubagentSpawnedEvent(
        **_build_subagent_event_fields(
            payload=payload,
            status=SUBAGENT_STATUS_ACCEPTED,
            status_message="Accepted",
            result_text=payload.result_text,
            result_text_delta=payload.result_text_delta,
        ),
    )
