"""SoAI - Agent turn todo-state conversion helpers [backend/features/agent/runtime/turn_todo_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.state_payloads import read_agent_todo_payload
from core.agent.todo_state_models import AgentTurnTodoState
from core.agent.todo_state_parsing import (
    parse_agent_todo_state_from_turn_record,
    parse_agent_todo_state_payload,
    render_agent_todo_state_payload,
)
from core.errors.exceptions import StateError, ValidationError

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import (
        DatabaseAgentTodoStateProtocol,
    )
    from core.types.json import JSONDict

__all__ = (
    "build_todo_payload_for_turn_record",
    "build_turn_todo_state_from_turn_record",
    "load_turn_todo_state",
    "parse_agent_todo_state_payload",
)


def build_turn_todo_state_from_turn_record(turn_record: JSONDict | None) -> AgentTurnTodoState:
    if not isinstance(turn_record, dict):
        raise StateError("Agent turn todo state record is invalid.")
    try:
        todo_state = parse_agent_todo_state_from_turn_record(turn_record)
    except ValidationError as exception:
        raise StateError(str(exception)) from exception
    return todo_state


async def load_turn_todo_state(
    *,
    database_agent_todo_state: DatabaseAgentTodoStateProtocol,
    conv_id: str,
    user_id: int,
) -> AgentTurnTodoState:
    payload = await read_agent_todo_payload(
        database_agent_todo_state=database_agent_todo_state,
        conv_id=conv_id,
        user_id=user_id,
    )
    return parse_agent_todo_state_payload(payload)


def build_todo_payload_for_turn_record(
    *,
    todo: list[JSONDict],
    explanation: str | None,
    revision: int,
    updated_at_ms: int | None,
) -> JSONDict:
    return render_agent_todo_state_payload(
        AgentTurnTodoState(
            todo=todo,
            todo_explanation=explanation,
            todo_revision=revision,
            todo_updated_at_ms=updated_at_ms,
        ),
    )
