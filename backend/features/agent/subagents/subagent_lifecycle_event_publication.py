"""SoAI - Subagent lifecycle realtime event publication [backend/features/agent/subagents/subagent_lifecycle_event_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import (
    SUBAGENT_STATUS_RUNNING,
    SUBAGENT_TERMINAL_STATUSES,
)
from core.errors.exceptions import ValidationError
from core.runtime.request_context import RequestContext
from features.agent.events.subagent_types import (
    SubagentAbandonedEvent,
    SubagentCancelledEvent,
    SubagentCompletedEvent,
    SubagentErrorEvent,
    SubagentMaxIterationsEvent,
)
from features.agent.runtime.turn_engine import publish_agent_event
from features.agent.subagents.event_payload_factories import (
    build_subagent_spawned_event,
)
from features.agent.subagents.event_payloads import (
    SubagentEventPayload,
    build_subagent_event_payload,
    build_subagent_terminal_event,
    read_snapshot_text,
)
from features.agent.subagents.snapshots import build_subagent_snapshot

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.execution.protocols import SubagentSnapshot
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict

__all__ = (
    "publish_subagent_spawned_event",
    "publish_subagent_terminal_event",
)


def _build_terminal_event(
    *,
    status: str,
    payload: SubagentEventPayload,
) -> (
    SubagentAbandonedEvent
    | SubagentCancelledEvent
    | SubagentCompletedEvent
    | SubagentErrorEvent
    | SubagentMaxIterationsEvent
):
    return build_subagent_terminal_event(status=status, payload=payload)


async def _publish_terminal_status_event(
    *,
    event_bus: EventBusProtocol,
    logger: LoggerProtocol,
    status: str,
    payload: SubagentEventPayload,
) -> None:
    event_obj = _build_terminal_event(status=status, payload=payload)
    await publish_agent_event(
        event_bus=event_bus,
        logger=logger,
        event_obj=event_obj,
    )


def _require_subagent_tool_context(context: RequestContext) -> MCPToolContext:
    tool_context = context.mcp_tool_context
    if tool_context is None:
        raise ValidationError("Subagent event publication requires an active tool context.")
    return tool_context


async def publish_subagent_spawned_event(
    *,
    event_bus: EventBusProtocol,
    logger: LoggerProtocol,
    parent_tool_context: MCPToolContext,
    snapshot: SubagentSnapshot,
) -> None:
    payload = build_subagent_event_payload(
        snapshot=snapshot,
        user_id=parent_tool_context.user_id,
        conv_id=parent_tool_context.conv_id,
        result_text=None,
        error_message=None,
        token_usage=None,
        updated_at_ms_override=None,
    )
    await publish_agent_event(
        event_bus=event_bus,
        logger=logger,
        event_obj=build_subagent_spawned_event(payload=payload),
    )


async def publish_subagent_terminal_event(
    *,
    event_bus: EventBusProtocol,
    logger: LoggerProtocol,
    context: RequestContext,
    turn_record: JSONDict | None,
    token_usage: JSONDict | None,
    updated_at_ms_override: int | None = None,
) -> None:
    snapshot = build_subagent_snapshot(turn_record)
    if snapshot is None:
        return
    status = snapshot.status
    if status == SUBAGENT_STATUS_RUNNING or status not in SUBAGENT_TERMINAL_STATUSES:
        return
    resolved_updated_at_ms_override = updated_at_ms_override
    finished_at_ms = snapshot.finished_at_ms
    if (
        resolved_updated_at_ms_override is not None
        and isinstance(finished_at_ms, int)
        and not isinstance(finished_at_ms, bool)
        and resolved_updated_at_ms_override > finished_at_ms
    ):
        resolved_updated_at_ms_override = int(finished_at_ms)
    tool_context = _require_subagent_tool_context(context)
    event_payload = build_subagent_event_payload(
        snapshot=snapshot,
        user_id=context.user_id,
        conv_id=tool_context.conv_id,
        result_text=read_snapshot_text(snapshot.result_text),
        error_message=read_snapshot_text(snapshot.error_message),
        token_usage=token_usage,
        updated_at_ms_override=resolved_updated_at_ms_override,
    )
    await _publish_terminal_status_event(
        event_bus=event_bus,
        logger=logger,
        status=status,
        payload=event_payload,
    )
