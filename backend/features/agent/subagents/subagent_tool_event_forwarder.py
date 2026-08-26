"""SoAI - Subagent tool event forwarding to parent structured updates [backend/features/agent/subagents/subagent_tool_event_forwarder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.events.tool_call_event_guards import is_tool_call_stream_event
from core.events.types_base import Event
from core.events.types_system import (
    ToolCallCompletedEvent,
    ToolCallCreatedEvent,
    ToolCallOutputDeltaEvent,
    ToolCallStartedEvent,
)
from core.timing.epoch import epoch_ms
from core.tool_calls.status_values import TOOL_CALL_STATUS_RUNNING
from features.agent.subagents.parent_tool_call_updates import (
    SubagentParentToolCallUpdateBridge,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol

__all__ = ("SubagentToolEventForwarder",)

_SUBAGENT_FORWARDED_EVENT_TOOL_DENYLIST_PREFIXES: tuple[str, ...] = ("subagent_",)


def _is_forwardable_tool_name(tool_name: str) -> bool:
    normalized = str(tool_name or "").strip()
    if not normalized:
        return False
    for prefix in _SUBAGENT_FORWARDED_EVENT_TOOL_DENYLIST_PREFIXES:
        if normalized.startswith(prefix):
            return False
    return True


@dataclass(slots=True)
class SubagentToolEventForwarder:
    event_bus: EventBusProtocol
    subagent_turn_id: str
    subagent_conv_id: str
    subagent_user_id: int
    bridge: SubagentParentToolCallUpdateBridge
    _subscribed: bool = False
    _handler: (
        Callable[
            [Event],
            Awaitable[None],
        ]
        | None
    ) = None

    def subscribe(self) -> None:
        if self._subscribed:
            return
        normalized_turn_id = str(self.subagent_turn_id or "").strip()
        if not normalized_turn_id:
            raise ValidationError("Subagent tool event forwarder requires subagent_turn_id.")
        normalized_conv_id = str(self.subagent_conv_id or "").strip()
        if not normalized_conv_id:
            raise ValidationError("Subagent tool event forwarder requires subagent_conv_id.")
        normalized_user_id = int(self.subagent_user_id)

        async def handler(
            event: Event,
        ) -> None:
            if not is_tool_call_stream_event(event):
                return
            event_turn_id = event.turn_id.strip() if isinstance(event.turn_id, str) else ""
            if event_turn_id != normalized_turn_id:
                return
            event_conv_id = event.conv_id.strip() if isinstance(event.conv_id, str) else ""
            if event_conv_id != normalized_conv_id:
                return
            if int(event.user_id) != normalized_user_id:
                return
            tool_name = event.tool_name.strip() if isinstance(event.tool_name, str) else ""
            if not _is_forwardable_tool_name(tool_name):
                return

            if isinstance(event, ToolCallCreatedEvent):
                await self.bridge.publish_child_tool_call_update_noncritical(
                    call_id=event.call_id,
                    tool_name=tool_name,
                    sequence_index=event.sequence_index,
                    content_index_before=event.content_index_before,
                    started_at_ms=epoch_ms(),
                    duration_ms=None,
                    status="pending",
                    arguments_payload=event.tool_arguments,
                    result_payload=None,
                    code_diffs=None,
                    error_message=None,
                    output_delta=None,
                )
                return
            if isinstance(event, ToolCallStartedEvent):
                await self.bridge.publish_child_tool_call_update_noncritical(
                    call_id=event.call_id,
                    tool_name=tool_name,
                    sequence_index=event.sequence_index,
                    content_index_before=event.content_index_before,
                    started_at_ms=event.started_at_ms,
                    duration_ms=None,
                    status=TOOL_CALL_STATUS_RUNNING,
                    arguments_payload=event.tool_arguments,
                    result_payload=None,
                    code_diffs=None,
                    error_message=None,
                    output_delta=None,
                )
                return
            if isinstance(event, ToolCallCompletedEvent):
                await self.bridge.publish_child_tool_call_update_noncritical(
                    call_id=event.call_id,
                    tool_name=tool_name,
                    sequence_index=event.sequence_index,
                    content_index_before=event.content_index_before,
                    started_at_ms=None,
                    duration_ms=event.duration_ms,
                    status=event.status,
                    arguments_payload=None,
                    result_payload=event.result,
                    code_diffs=event.code_diffs,
                    error_message=event.error_message,
                    output_delta=None,
                )
                return
            if isinstance(event, ToolCallOutputDeltaEvent):
                await self.bridge.publish_child_tool_call_update_noncritical(
                    call_id=event.call_id,
                    tool_name=tool_name,
                    sequence_index=None,
                    content_index_before=None,
                    started_at_ms=None,
                    duration_ms=None,
                    status=None,
                    arguments_payload=None,
                    result_payload=None,
                    code_diffs=None,
                    error_message=None,
                    output_delta=event.delta,
                )
                return

        for event_type in (
            ToolCallCreatedEvent,
            ToolCallStartedEvent,
            ToolCallCompletedEvent,
            ToolCallOutputDeltaEvent,
        ):
            self.event_bus.subscribe(event_type, handler)
        self._subscribed = True
        self._handler = handler

    def unsubscribe(self) -> None:
        if not self._subscribed:
            return
        handler = self._handler
        if handler is None:
            self._subscribed = False
            return
        for event_type in (
            ToolCallCreatedEvent,
            ToolCallStartedEvent,
            ToolCallCompletedEvent,
            ToolCallOutputDeltaEvent,
        ):
            self.event_bus.unsubscribe(event_type, handler)
        self._subscribed = False
        self._handler = None
