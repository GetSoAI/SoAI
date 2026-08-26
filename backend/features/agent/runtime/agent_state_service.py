"""SoAI - Shared persisted agent state service [backend/features/agent/runtime/agent_state_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.state_payloads import (
    read_agent_plan_payload,
    read_agent_todo_payload,
)
from core.agent.state_persistence import (
    persist_agent_plan_write,
    persist_agent_todo_write,
)
from core.di.validation import require_dependencies
from features.agent.events.types import AgentPlanUpdatedEvent, AgentTodoUpdatedEvent
from features.agent.runtime.agent_state_manual_edit_policy import (
    ensure_manual_edit_allowed,
)

if TYPE_CHECKING:
    from core.agent.protocols import PersistedAgentStateProtocol
    from core.conversations.protocols_database_agents import (
        DatabaseAgentEventSequencesProtocol,
        DatabaseAgentPlanProtocol,
        DatabaseAgentTodoStateProtocol,
        DatabaseAgentTurnsProtocol,
    )
    from core.tasks.protocols import TokenCollectionProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "AgentStateService",
    "AgentStateServiceDependencies",
    "PersistedAgentPlanState",
    "PersistedAgentTodoState",
)


@dataclass(frozen=True, slots=True)
class AgentStateServiceDependencies:
    database_agent_event_sequences: DatabaseAgentEventSequencesProtocol
    database_agent_plan: DatabaseAgentPlanProtocol
    database_agent_todo_state: DatabaseAgentTodoStateProtocol
    database_agent_turns: DatabaseAgentTurnsProtocol | None = None
    database_tool_calls: DatabaseToolCallsProtocol | None = None
    task_registry_queries: TaskRegistryQueryView | None = None
    token_collection: TokenCollectionProtocol | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="AgentStateServiceDependencies",
            database_agent_event_sequences=self.database_agent_event_sequences,
            database_agent_plan=self.database_agent_plan,
            database_agent_todo_state=self.database_agent_todo_state,
        )


@dataclass(frozen=True, slots=True)
class PersistedAgentTodoState:
    payload: JSONDict
    event: AgentTodoUpdatedEvent


@dataclass(frozen=True, slots=True)
class PersistedAgentPlanState:
    payload: JSONDict
    event: AgentPlanUpdatedEvent


class AgentStateService:
    def __init__(self, deps: AgentStateServiceDependencies) -> None:
        self._database_agent_event_sequences = deps.database_agent_event_sequences
        self._database_agent_plan = deps.database_agent_plan
        self._database_agent_todo_state = deps.database_agent_todo_state
        self._database_agent_turns = deps.database_agent_turns
        self._database_tool_calls = deps.database_tool_calls
        self._task_registry_queries = deps.task_registry_queries
        self._token_collection = deps.token_collection

    async def get_todo_payload(self, *, conv_id: str, user_id: int) -> JSONDict:
        return await read_agent_todo_payload(
            database_agent_todo_state=self._database_agent_todo_state,
            conv_id=conv_id,
            user_id=user_id,
        )

    async def read_plan_payload(self, *, conv_id: str, user_id: int) -> JSONDict:
        return await read_agent_plan_payload(
            database_agent_plan=self._database_agent_plan,
            conv_id=conv_id,
            user_id=user_id,
        )

    async def persist_todo_state(
        self,
        *,
        conv_id: str,
        user_id: int,
        turn_id: str,
        iteration_index: int,
        todo_value: JSONValue,
        explanation_value: JSONValue,
        require_no_running_root_turn: bool,
    ) -> PersistedAgentStateProtocol:
        if require_no_running_root_turn:
            await ensure_manual_edit_allowed(
                database_agent_turns=self._database_agent_turns,
                database_tool_calls=self._database_tool_calls,
                task_registry_queries=self._task_registry_queries,
                token_collection=self._token_collection,
                conv_id=conv_id,
                user_id=user_id,
            )
        persisted_write = await persist_agent_todo_write(
            database_agent_event_sequences=self._database_agent_event_sequences,
            database_agent_todo_state=self._database_agent_todo_state,
            conv_id=conv_id,
            user_id=user_id,
            todo_value=todo_value,
            explanation_value=explanation_value,
            require_no_running_root_turn=require_no_running_root_turn,
        )
        return PersistedAgentTodoState(
            payload=persisted_write.payload,
            event=AgentTodoUpdatedEvent(
                user_id=int(user_id),
                conv_id=conv_id,
                turn_id=turn_id,
                iteration_index=int(iteration_index),
                sequence=int(persisted_write.revision),
                revision=int(persisted_write.revision),
                explanation=persisted_write.explanation,
                todo=[dict(entry) for entry in persisted_write.todo],
            ),
        )

    async def persist_plan_state(
        self,
        *,
        conv_id: str,
        user_id: int,
        turn_id: str,
        iteration_index: int,
        title_value: JSONValue,
        markdown_value: JSONValue,
        require_no_running_root_turn: bool,
    ) -> PersistedAgentStateProtocol:
        if require_no_running_root_turn:
            await ensure_manual_edit_allowed(
                database_agent_turns=self._database_agent_turns,
                database_tool_calls=self._database_tool_calls,
                task_registry_queries=self._task_registry_queries,
                token_collection=self._token_collection,
                conv_id=conv_id,
                user_id=user_id,
            )
        persisted_write = await persist_agent_plan_write(
            database_agent_event_sequences=self._database_agent_event_sequences,
            database_agent_plan=self._database_agent_plan,
            conv_id=conv_id,
            user_id=user_id,
            title_value=title_value,
            markdown_value=markdown_value,
            require_no_running_root_turn=require_no_running_root_turn,
        )
        return PersistedAgentPlanState(
            payload=persisted_write.payload,
            event=AgentPlanUpdatedEvent(
                user_id=int(user_id),
                conv_id=conv_id,
                turn_id=turn_id,
                iteration_index=int(iteration_index),
                sequence=int(persisted_write.revision),
                revision=int(persisted_write.revision),
                title=persisted_write.title,
                markdown=persisted_write.markdown,
            ),
        )
