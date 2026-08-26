"""SoAI - Shared agent state persistence operations [backend/core/agent/state_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.state_errors import AgentStateRevisionConflictError
from core.agent.state_payloads import (
    build_persisted_agent_plan_payload,
    build_persisted_agent_todo_payload,
    next_agent_state_updated_at_ms,
    reserve_agent_state_revision,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import (
        DatabaseAgentEventSequencesProtocol,
        DatabaseAgentPlanProtocol,
        DatabaseAgentTodoStateProtocol,
    )
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "PersistedAgentPlanWrite",
    "PersistedAgentTodoWrite",
    "persist_agent_plan_write",
    "persist_agent_todo_write",
)


@dataclass(frozen=True, slots=True)
class PersistedAgentPlanWrite:
    revision: int
    updated_at_ms: int
    payload: JSONDict
    title: str | None
    markdown: str | None


@dataclass(frozen=True, slots=True)
class PersistedAgentTodoWrite:
    revision: int
    updated_at_ms: int
    payload: JSONDict
    explanation: str | None
    todo: list[JSONDict]


async def persist_agent_plan_write(
    *,
    database_agent_event_sequences: DatabaseAgentEventSequencesProtocol,
    database_agent_plan: DatabaseAgentPlanProtocol,
    conv_id: str,
    user_id: int,
    title_value: JSONValue,
    markdown_value: JSONValue,
    require_no_running_root_turn: bool,
) -> PersistedAgentPlanWrite:
    revision = await reserve_agent_state_revision(
        database_agent_event_sequences=database_agent_event_sequences,
        conv_id=conv_id,
        user_id=user_id,
    )
    updated_at_ms = next_agent_state_updated_at_ms()
    normalized_state = build_persisted_agent_plan_payload(
        conv_id=conv_id,
        user_id=user_id,
        revision=revision,
        updated_at_ms=updated_at_ms,
        title_value=title_value,
        markdown_value=markdown_value,
    )
    persisted = (
        await database_agent_plan.upsert_plan_if_no_running_turn(
            conv_id=conv_id,
            user_id=user_id,
            revision=revision,
            updated_at_ms=updated_at_ms,
            title=normalized_state.title,
            markdown=normalized_state.markdown,
        )
        if require_no_running_root_turn
        else await database_agent_plan.upsert_plan(
            conv_id=conv_id,
            user_id=user_id,
            revision=revision,
            updated_at_ms=updated_at_ms,
            title=normalized_state.title,
            markdown=normalized_state.markdown,
        )
    )
    if not persisted:
        raise AgentStateRevisionConflictError()
    return PersistedAgentPlanWrite(
        revision=int(revision),
        updated_at_ms=int(updated_at_ms),
        payload=normalized_state.payload,
        title=normalized_state.title,
        markdown=normalized_state.markdown,
    )


async def persist_agent_todo_write(
    *,
    database_agent_event_sequences: DatabaseAgentEventSequencesProtocol,
    database_agent_todo_state: DatabaseAgentTodoStateProtocol,
    conv_id: str,
    user_id: int,
    todo_value: JSONValue,
    explanation_value: JSONValue,
    require_no_running_root_turn: bool,
) -> PersistedAgentTodoWrite:
    revision = await reserve_agent_state_revision(
        database_agent_event_sequences=database_agent_event_sequences,
        conv_id=conv_id,
        user_id=user_id,
    )
    updated_at_ms = next_agent_state_updated_at_ms()
    normalized_state = build_persisted_agent_todo_payload(
        conv_id=conv_id,
        user_id=user_id,
        revision=revision,
        updated_at_ms=updated_at_ms,
        todo_value=todo_value,
        explanation_value=explanation_value,
    )
    persisted = (
        await database_agent_todo_state.upsert_todo_state_if_no_running_turn(
            conv_id=conv_id,
            user_id=user_id,
            revision=revision,
            updated_at_ms=updated_at_ms,
            explanation=normalized_state.explanation,
            todo=list(normalized_state.todo),
        )
        if require_no_running_root_turn
        else await database_agent_todo_state.upsert_todo_state(
            conv_id=conv_id,
            user_id=user_id,
            revision=revision,
            updated_at_ms=updated_at_ms,
            explanation=normalized_state.explanation,
            todo=list(normalized_state.todo),
        )
    )
    if not persisted:
        raise AgentStateRevisionConflictError()
    return PersistedAgentTodoWrite(
        revision=int(revision),
        updated_at_ms=int(updated_at_ms),
        payload=normalized_state.payload,
        explanation=normalized_state.explanation,
        todo=list(normalized_state.todo),
    )
