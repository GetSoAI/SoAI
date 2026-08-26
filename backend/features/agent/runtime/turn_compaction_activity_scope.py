"""SoAI - Auto-compaction lifecycle dependency scope [backend/features/agent/runtime/turn_compaction_activity_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.runtime.request_context_cloning import clone_request_context

if TYPE_CHECKING:
    from core.agent.turn_state_writer import TurnStateWriter
    from core.events.types_base import Event
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.tool_calls.protocols import DatabaseToolCallsProtocol

__all__ = (
    "AutoCompactionActivityScope",
    "build_auto_compaction_activity_scope",
)


@dataclass(frozen=True, slots=True)
class AutoCompactionActivityScope:
    user_id: int
    conv_id: str
    message_index: int
    turn_id: str
    iteration_index: int
    request_context: RequestContext
    tool_context: MCPToolContext
    database_tool_calls: DatabaseToolCallsProtocol
    next_action_sequence: Callable[[], Awaitable[int]]
    publish_event: Callable[[Event], Awaitable[None]]
    turn_state_writer: TurnStateWriter

    def clone_for_iteration_request_context(self) -> AutoCompactionActivityScope:
        return AutoCompactionActivityScope(
            user_id=self.user_id,
            conv_id=self.conv_id,
            message_index=self.message_index,
            turn_id=self.turn_id,
            iteration_index=self.iteration_index,
            request_context=clone_request_context(
                self.request_context,
                agent_iteration_index=self.iteration_index,
            ),
            tool_context=self.tool_context,
            database_tool_calls=self.database_tool_calls,
            next_action_sequence=self.next_action_sequence,
            publish_event=self.publish_event,
            turn_state_writer=self.turn_state_writer,
        )


def build_auto_compaction_activity_scope(
    *,
    user_id: int,
    conv_id: str,
    message_index: int,
    turn_id: str,
    iteration_index: int,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    database_tool_calls: DatabaseToolCallsProtocol,
    next_action_sequence: Callable[[], Awaitable[int]],
    publish_event: Callable[[Event], Awaitable[None]],
    turn_state_writer: TurnStateWriter,
) -> AutoCompactionActivityScope:
    return AutoCompactionActivityScope(
        user_id,
        conv_id,
        message_index,
        turn_id,
        iteration_index,
        request_context,
        tool_context,
        database_tool_calls,
        next_action_sequence,
        publish_event,
        turn_state_writer,
    ).clone_for_iteration_request_context()
