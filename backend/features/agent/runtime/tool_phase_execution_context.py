"""SoAI - Agent tool phase execution context [backend/features/agent/runtime/tool_phase_execution_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.agent.turn_state_writer import TurnStateWriter
    from core.conversations.protocols_database_conversation_inputs import (
        DatabaseConversationInputsProtocol,
    )
    from core.events.types_base import Event
    from core.logging.protocols import LoggerProtocol
    from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import CancellationHistoryProtocol
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.tool_calls.protocols import (
        DatabaseToolCallsProtocol,
        ToolCallProcessingProtocol,
    )
    from core.tool_calls.tool_result_prompt_cache import ToolResultPromptShapeCache
    from core.types.json import JSONDict
    from core.users.protocols_database import DatabaseUsersProtocol
    from features.agent.runtime.turn_engine import (
        ActionSequenceTracker,
        AgentTurnTodoState,
        TurnPrimitives,
    )

__all__ = ("ToolPhaseExecutionContext",)


@dataclass(frozen=True, slots=True)
class ToolPhaseExecutionContext:
    request_context: RequestContext
    tool_context: MCPToolContext
    tool_call_processor: ToolCallProcessingProtocol
    database_tool_calls: DatabaseToolCallsProtocol
    task_registry: TaskRegistryProtocol | None
    database_notifications: DatabaseNotificationsProtocol
    conversation_attention: ConversationAttentionCoordinatorProtocol
    database_input_queue: DatabaseConversationInputsProtocol
    database_users: DatabaseUsersProtocol | None
    logger: LoggerProtocol
    cancellation_history: CancellationHistoryProtocol | None
    current_cancellation_id: str
    iteration_index: int
    assistant_text: str | None
    tool_calls: list[JSONDict]
    message_history: list[JSONDict]
    boundary_source_messages: list[JSONDict]
    todo_state: AgentTurnTodoState
    primitives: TurnPrimitives
    sequence_tracker: ActionSequenceTracker
    turn_state_writer: TurnStateWriter
    emit_event: Callable[[Event], Awaitable[None]]
    turn_cancelled: Callable[[], Awaitable[bool]]
    shape_cache: ToolResultPromptShapeCache
