"""SoAI - Agent turn engine primitives [backend/features/agent/runtime/turn_engine.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.protocols import AgentChronologySequencerProtocol
from core.agent.todo_state_models import AgentTurnTodoState
from core.conversations.protocols_database_agents import (
    DatabaseAgentPlanProtocol,
    DatabaseAgentTodoStateProtocol,
    DatabaseAgentTurnsProtocol,
)
from core.conversations.protocols_database_conversation_inputs import (
    DatabaseConversationInputsProtocol,
)
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol
from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
from core.notifications.protocols_database import DatabaseNotificationsProtocol
from core.orchestrator.types import MCPToolContext
from core.runtime.cancellation_ids import build_agent_turn_cancellation_id
from core.runtime.protocols import RequestContextProtocol
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.tasks.protocols import (
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)
from core.tasks.protocols_query import TaskRegistryQueryView
from core.tool_calls.protocols import (
    DatabaseToolCallsProtocol,
    ToolCallProcessingProtocol,
)
from core.users.protocols_database import DatabaseUsersProtocol
from core.users.user_id import require_user_id
from features.agent.runtime.turn_sequence import coerce_turn_sequence

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.events.protocols import EventBusProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.types.json import JSONDict

__all__ = (
    "ActionSequenceTracker",
    "AgentTurnEngineDependencies",
    "AgentTurnResult",
    "AgentTurnTodoState",
    "TurnPrimitives",
    "build_action_sequence_tracker",
    "build_turn_cancelled_check",
    "coerce_conv_id",
    "create_turn_execution_token",
    "create_turn_id",
    "publish_agent_event",
    "require_base_cancellation_id",
    "resolve_existing_turn_id",
    "resolve_turn_primitives",
)

OPERATION = "agent.turn_engine.publish_event"


@dataclass(frozen=True, slots=True)
class TurnPrimitives:
    start_time: float
    base_cancellation_id: str
    conv_id: str
    message_index: int
    user_id: int
    turn_id: str
    turn_cancellation_id: str


@dataclass(frozen=True, slots=True)
class AgentTurnEngineDependencies:
    database_agent_turns: DatabaseAgentTurnsProtocol
    database_tool_calls: DatabaseToolCallsProtocol
    database_agent_todo_state: DatabaseAgentTodoStateProtocol
    database_agent_plan: DatabaseAgentPlanProtocol
    database_notifications: DatabaseNotificationsProtocol
    conversation_attention: ConversationAttentionCoordinatorProtocol
    database_input_queue: DatabaseConversationInputsProtocol
    agent_chronology_sequencer: AgentChronologySequencerProtocol
    tool_call_processor: ToolCallProcessingProtocol
    prompt_token_counter: PromptTokenCounter
    event_bus: EventBusProtocol | None
    cancellation_history: CancellationHistoryProtocol | None
    token_collection: TokenCollectionProtocol
    task_cancellation_binder: TaskCancellationBinderProtocol
    task_registry_queries: TaskRegistryQueryView
    logger: LoggerProtocol
    database_users: DatabaseUsersProtocol | None = None
    task_registry: TaskRegistryProtocol | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="AgentTurnEngineDependencies",
            agent_chronology_sequencer=self.agent_chronology_sequencer,
            database_agent_turns=self.database_agent_turns,
            database_tool_calls=self.database_tool_calls,
            database_agent_todo_state=self.database_agent_todo_state,
            database_agent_plan=self.database_agent_plan,
            database_notifications=self.database_notifications,
            conversation_attention=self.conversation_attention,
            database_input_queue=self.database_input_queue,
            logger=self.logger,
            prompt_token_counter=self.prompt_token_counter,
            token_collection=self.token_collection,
            task_cancellation_binder=self.task_cancellation_binder,
            task_registry_queries=self.task_registry_queries,
            tool_call_processor=self.tool_call_processor,
        )


@dataclass(frozen=True, slots=True)
class AgentTurnResult:
    final_payload: JSONDict
    reached_max_iterations: bool


def create_turn_id() -> str:
    return create_prefixed_hex_id("turn", length=16)


def create_turn_execution_token() -> str:
    return create_prefixed_hex_id("exec", length=24)


async def publish_agent_event(
    *,
    event_bus: EventBusProtocol | None,
    logger: LoggerProtocol,
    event_obj: Event,
) -> None:
    if event_bus is None:
        return
    try:
        await event_bus.publish(event_obj)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to publish agent event (non-critical).",
            operation=OPERATION,
            level="debug",
        )


def coerce_conv_id(tool_context: MCPToolContext) -> str:
    conv_id_value = tool_context.conv_id
    conv_id = str(conv_id_value or "").strip()
    if not conv_id:
        raise ValidationError("conv_id must be configured for agent turn.")
    return conv_id


def require_base_cancellation_id(context: RequestContextProtocol) -> str:
    value = context.cancellation_id
    cancellation_id = str(value or "").strip()
    if not cancellation_id:
        raise ValidationError("cancellation_id must be available for agent turn.")
    return cancellation_id


def resolve_existing_turn_id(context: RequestContextProtocol) -> str | None:
    turn_id_value = context.agent_turn_id
    return turn_id_value if turn_id_value is not None and turn_id_value.strip() else None


def resolve_turn_primitives(
    *,
    context: RequestContextProtocol,
    tool_context: MCPToolContext,
    mode: str,
    turn_id: str | None,
) -> TurnPrimitives:
    start_time = time.monotonic()
    base_cancellation_id = require_base_cancellation_id(context)
    conv_id = coerce_conv_id(tool_context)
    user_id = require_user_id(tool_context.user_id)
    resolved_turn_id_value = turn_id.strip() if turn_id is not None else ""
    resolved_turn_id = resolved_turn_id_value or create_turn_id()
    turn_cancellation_id = build_agent_turn_cancellation_id(
        base_cancellation_id=base_cancellation_id,
        turn_id=resolved_turn_id,
        mode=mode,
    )
    return TurnPrimitives(
        start_time=start_time,
        base_cancellation_id=base_cancellation_id,
        conv_id=conv_id,
        message_index=int(tool_context.message_index),
        user_id=user_id,
        turn_id=resolved_turn_id,
        turn_cancellation_id=turn_cancellation_id,
    )


def build_turn_cancelled_check(
    cancellation_history: CancellationHistoryProtocol | None,
    turn_cancellation_id: str,
) -> Callable[[], Awaitable[bool]]:
    async def check() -> bool:
        if cancellation_history is None:
            return False
        return await cancellation_history.is_cancelled(turn_cancellation_id)

    return check


@dataclass(slots=True)
class ActionSequenceTracker:
    last_emitted_sequence: int
    sequencer: AgentChronologySequencerProtocol
    conv_id: str
    user_id: int

    async def next_sequence(self) -> int:
        sequence = await self.sequencer.next_sequence(
            conv_id=self.conv_id,
            user_id=self.user_id,
        )
        self.last_emitted_sequence = max(self.last_emitted_sequence, sequence)
        return sequence

    def resolve_turn_state_sequence(self) -> int:
        return int(self.last_emitted_sequence)


def build_action_sequence_tracker(
    *,
    sequencer: AgentChronologySequencerProtocol,
    conv_id: str,
    user_id: int,
    initial_turn_state: JSONDict | None,
) -> ActionSequenceTracker:
    turn_state_sequence = coerce_turn_sequence(initial_turn_state)
    peek_last_issued_value = sequencer.peek_last_issued(conv_id=conv_id, user_id=user_id)
    peek_last_issued = int(peek_last_issued_value or 0)
    last_emitted = max(int(turn_state_sequence), 0, peek_last_issued)
    return ActionSequenceTracker(
        last_emitted_sequence=last_emitted,
        sequencer=sequencer,
        conv_id=conv_id,
        user_id=user_id,
    )
